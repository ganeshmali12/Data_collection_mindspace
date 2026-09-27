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


from .audio_cleaner import build_audio_filter_chain, clean_audio_file, combine_and_clean_captures


def combine_audio(captures):
    """
    Combines phonation audio captures while applying bandpass filtering,
    spectral noise suppression, and normalization.
    """
    if len(captures) == 1:
        return clean_audio_file(captures[0].file.path, target_sr=16000)

    try:
        return combine_and_clean_captures(captures, target_sr=16000)
    except Exception as exc:
        logger_error = str(exc)
        # Fallback to direct FFmpeg concatenation with filter chain if needed
        output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        command = ["ffmpeg", "-y"]
        for capture in captures:
            command.extend(["-i", capture.file.path])
        inputs = "".join(f"[{index}:a]" for index in range(len(captures)))
        filter_chain = build_audio_filter_chain(lowcut=80, highcut=8000, enable_denoise=True, enable_silence_trim=False)
        command.extend([
            "-filter_complex", f"{inputs}concat=n={len(captures)}:v=0:a=1[out]",
            "-map", "[out]",
            "-af", filter_chain,
            "-ar", "16000", "-ac", "1", output_path,
        ])
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            return output_path
        except FileNotFoundError as fnf_exc:
            raise RuntimeError("FFmpeg is required to combine phonation audio.") from fnf_exc
        except subprocess.CalledProcessError as sub_exc:
            raise RuntimeError(f"Could not combine phonation recordings: {logger_error}") from sub_exc



def process_voice_session(session):
    captures = list(
        session.media_captures.filter(kind="phonation_audio").order_by("created_at")
    )
    if not captures:
        raise ValueError("Phonation audio recording is required.")

    result, _ = AnalysisResult.objects.update_or_create(
        session=session,
        modality="voice",
        defaults={"capture": captures[0], "status": "processing", "error_message": "", "started_at": timezone.now()},
    )
    combined_path = ""
    try:
        if len(captures) == 1:
            combined_path = clean_audio_file(captures[0].file.path, target_sr=16000)
        else:
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