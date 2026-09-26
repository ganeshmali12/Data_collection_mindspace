import os
import subprocess
import tempfile

from django.utils import timezone

from ..models import AnalysisResult, CollectionSession, MediaCapture
from .face_api import extract_features, get_session_vector, score_features
from .text_api import extract_parameters, score_parameters, transcribe_audio


def feature_payload(response):
    if isinstance(response, dict):
        for key in ("features", "vector", "feature_vector", "data"):
            value = response.get(key)
            if isinstance(value, (dict, list)):
                return value
    return response


def extract_audio_from_video(video_path):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as audio_file:
        audio_path = audio_file.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", audio_path],
            check=True,
            capture_output=True,
            text=True,
        )
        return audio_path
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg is required to extract spoken audio from video.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Could not extract audio from the uploaded video.") from exc


def process_combined_capture(capture_id, transcript=""):
    capture = MediaCapture.objects.select_related("session").get(pk=capture_id)
    session = capture.session
    session.status = "processing"
    session.current_step = "face_text_processing"
    session.save(update_fields=["status", "current_step", "updated_at"])

    face_result, _ = AnalysisResult.objects.update_or_create(
        session=session,
        modality="face",
        defaults={"capture": capture, "status": "processing", "error_message": "", "started_at": timezone.now()},
    )

    try:
        with capture.file.open("rb") as video_file:
            extraction = extract_features(video_file)
        session_id = extraction.get("session_id") if isinstance(extraction, dict) else None
        vector_response = get_session_vector(session_id) if session_id else extraction
        scoring = score_features(feature_payload(vector_response))
        face_result.raw_response = {
            "extraction": extraction,
            "vector": vector_response,
            "scoring": scoring,
        }
        face_result.normalized_result = scoring if isinstance(scoring, dict) else {"value": scoring}
        face_result.status = "completed"
        face_result.completed_at = timezone.now()
        face_result.save(update_fields=["raw_response", "normalized_result", "status", "completed_at", "updated_at"])
    except Exception as exc:
        face_result.status = "failed"
        face_result.error_message = str(exc)
        face_result.save(update_fields=["status", "error_message", "updated_at"])

    text_result, _ = AnalysisResult.objects.update_or_create(
        session=session,
        modality="text",
        defaults={"capture": capture, "status": "processing", "transcript": transcript, "error_message": "", "started_at": timezone.now()},
    )
    try:
        transcription_response = {}
        if not transcript.strip():
            # Use capture.file.path (absolute disk path) so FFmpeg can find the file.
            try:
                audio_path = extract_audio_from_video(capture.file.path)
                try:
                    with open(audio_path, "rb") as audio_file:
                        transcript = transcribe_audio(audio_file)
                finally:
                    try:
                        os.remove(audio_path)
                    except OSError:
                        pass
            except Exception as stt_err:
                transcript = ""

        if transcript.strip():
            extraction = extract_parameters(transcript)
            scoring = score_parameters(feature_payload(extraction))
        else:
            extraction = {"features": {"data": {}}}
            scoring = {"score": 0.0, "note": "No speech detected in video."}

        text_result.transcript = transcript
        text_result.raw_response = {"transcription": transcription_response, "extraction": extraction, "scoring": scoring}
        text_result.normalized_result = scoring if isinstance(scoring, dict) else {"value": scoring}
        text_result.status = "completed"
        text_result.completed_at = timezone.now()
        text_result.save(update_fields=["transcript", "raw_response", "normalized_result", "status", "completed_at", "updated_at"])
    except Exception as exc:
        text_result.transcript = transcript
        text_result.raw_response = {"extraction": {"features": {"data": {}}}, "error": str(exc)}
        text_result.normalized_result = {"score": 0.0}
        text_result.status = "completed"
        text_result.completed_at = timezone.now()
        text_result.save(update_fields=["transcript", "raw_response", "normalized_result", "status", "completed_at", "updated_at"])

    session.status = "capture"
    session.current_step = "voice_phonation"
    session.save(update_fields=["status", "current_step", "updated_at"])
    return session