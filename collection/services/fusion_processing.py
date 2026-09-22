from django.utils import timezone

from ..models import AnalysisResult
from .fusion_api import score_fusion


def nested_features(payload, keys):
    if not isinstance(payload, dict):
        return {}
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}




# Text feature keys returned by the text extraction API differ from the
# names the fusion model expects for three features.
_TEXT_KEY_REMAP = {
    "hapax_legomena_ratio": "hapax_legoman_ratio",
    "repetition_ratio": "repetition_rate",
    "type_token_ratio": "type_token_ratio_ttr",
}

# The text extraction API does not return topic_shift_frequency.
# The fusion model requires it, so we default it to 0.0.
_TEXT_DEFAULTS = {
    "topic_shift_frequency": 0.0,
}


def _aggregate_face_features(raw_face_vector):
    """Collapse face features from suffix form (blink_rate__mean, blink_rate__slope)
    into a single scalar per base name.  Priority: mean > slope > max > first value.
    """
    from collections import defaultdict
    grouped = defaultdict(dict)
    for key, value in raw_face_vector.items():
        if "__" in key:
            base, suffix = key.split("__", 1)
        else:
            base, suffix = key, "val"
        try:
            grouped[base][suffix] = float(value)
        except (TypeError, ValueError):
            pass
    result = {}
    for base, variants in grouped.items():
        val = variants.get("mean", variants.get("slope", variants.get("max", next(iter(variants.values())))))
        result[base] = float(val)
    return result


def build_fusion_features(face, text, voice):
    # Face: the vector lives inside raw_response["vector"]["vector"]
    face_raw = face.raw_response.get("vector", {})
    face_vector = face_raw.get("vector", {}) if isinstance(face_raw, dict) else {}
    if not face_vector:
        face_vector = nested_features(face.raw_response.get("extraction"), ("features", "vector", "data"))
    face_features = _aggregate_face_features(face_vector) if face_vector else {}

    # Text: scalar features only; rename 3 keys; fill 1 missing key with 0.0
    text_raw = nested_features(text.raw_response.get("extraction"), ("features", "data"))
    text_features = dict(_TEXT_DEFAULTS)
    for key, value in text_raw.items():
        mapped_key = _TEXT_KEY_REMAP.get(key, key)
        try:
            text_features[mapped_key] = float(value)
        except (TypeError, ValueError):
            pass

    # Voice: PC1-PC24 directly from PCA output
    voice_features = nested_features(voice.raw_response.get("pca"), ("components", "pca_components", "features", "data"))

    features = {}
    for index in range(1, 25):
        key = f"PC{index}"
        features[key] = float(voice_features.get(key, 0) or 0)
    features.update(text_features)
    features.update(face_features)
    return features



def process_fusion_session(session):
    results = {
        result.modality: result
        for result in session.analysis_results.filter(status="completed", modality__in=["face", "text", "voice"])
    }
    missing = [modality for modality in ("face", "text", "voice") if modality not in results]
    if missing:
        raise ValueError(f"Missing completed results: {', '.join(missing)}.")

    fusion, _ = AnalysisResult.objects.update_or_create(
        session=session,
        modality="multimodal",
        defaults={"status": "processing", "error_message": "", "started_at": timezone.now()},
    )
    try:
        features = build_fusion_features(results["face"], results["text"], results["voice"])
        scoring = score_fusion(features)
        fusion.raw_response = {"features": features, "scoring": scoring}
        fusion.normalized_result = scoring if isinstance(scoring, dict) else {"value": scoring}
        fusion.status = "completed"
        fusion.completed_at = timezone.now()
        fusion.save(update_fields=["raw_response", "normalized_result", "status", "completed_at", "updated_at"])
        session.status = "completed"
        session.current_step = "completed"
        session.save(update_fields=["status", "current_step", "updated_at"])
    except Exception as exc:
        fusion.status = "failed"
        fusion.error_message = str(exc)
        fusion.save(update_fields=["status", "error_message", "updated_at"])
        session.status = "failed"
        session.current_step = "multimodal_processing_failed"
        session.save(update_fields=["status", "current_step", "updated_at"])
        raise
    return fusion