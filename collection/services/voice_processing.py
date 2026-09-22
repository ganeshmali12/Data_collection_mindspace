import os
import subprocess
import tempfile

from django.utils import timezone

from ..models import AnalysisResult, MediaCapture
from .voice_api import extract_features, process_pca, score_features


def feature_payload(response):
    if isinstance(response, dict):
        for key in ("features", "raw_features", "vector", "data"):
            value = response.get(key)
            if isinstance(value, (dict, list)):
                return value
    return response


def pca_payload(response):
    if isinstance(response, dict):
        for key in ("components", "pca_components", "features", "data"):
            value = response.get(key)
            if isinstance(value, dict):
                return value
    return response


def combine_audio(captures):
    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    command = ["ffmpeg", "-y"]
    for capture in captures:
        command.extend(["-i", capture.file.path])
    inputs = "".join(f"[{index}:a]" for index in range(len(captures)))
    command.extend([
        "-filter_complex", f"{inputs}concat=n={len(captures)}:v=0:a=1[out]",
        "-map", "[out]", "-ar", "16000", "-ac", "1", output_path,
    ])
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        return output_path
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg is required to combine phonation audio.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Could not combine phonation recordings.") from exc


def process_voice_session(session):
    captures = list(
        session.media_captures.filter(kind="phonation_audio").order_by("created_at")[:7]
    )
    if len(captures) < 7:
        raise ValueError(f"Seven phonation recordings are required. Found {len(captures)}.")

    result, _ = AnalysisResult.objects.update_or_create(
        session=session,
        modality="voice",
        defaults={"capture": captures[0], "status": "processing", "error_message": "", "started_at": timezone.now()},
    )
    combined_path = ""
    try:
        combined_path = combine_audio(captures)
        with open(combined_path, "rb") as audio_file:
            extraction = extract_features(audio_file)
        raw_features = feature_payload(extraction)
        pca = process_pca(raw_features)
        components = pca_payload(pca)
        scoring = score_features(components)
        result.raw_response = {"extraction": extraction, "pca": pca, "scoring": scoring}
        result.normalized_result = scoring if isinstance(scoring, dict) else {"value": scoring}
        result.status = "completed"
        result.completed_at = timezone.now()
        result.save(update_fields=["raw_response", "normalized_result", "status", "completed_at", "updated_at"])
        session.status = "processing"
        session.current_step = "multimodal_processing"
        session.save(update_fields=["status", "current_step", "updated_at"])
    except Exception as exc:
        result.status = "failed"
        result.error_message = str(exc)
        result.save(update_fields=["status", "error_message", "updated_at"])
        session.status = "failed"
        session.current_step = "voice_processing_failed"
        session.save(update_fields=["status", "current_step", "updated_at"])
        raise
    finally:
        if combined_path:
            try:
                os.remove(combined_path)
            except OSError:
                pass

    return result