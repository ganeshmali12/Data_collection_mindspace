import json
import os
import tempfile

from .http import configured, post_json


def transcribe_audio(audio_file, suffix=".wav"):
    try:
        from sarvamai import SarvamAI
    except ImportError as exc:
        raise RuntimeError("Speech-to-text requires the sarvamai package.") from exc

    api_key = configured("SARVAM_API_KEY")
    if not api_key:
        raise RuntimeError("SARVAM_API_KEY is not configured.")

    temp_path = ""
    output_dir = ""
    try:
        audio_file.seek(0)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            temp_file.write(audio_file.read())

        client = SarvamAI(api_subscription_key=api_key)
        job = client.speech_to_text_job.create_job(
            model=configured("SARVAM_STT_MODEL") or "saaras:v3",
            mode="transcribe",
            language_code="unknown",
        )
        if not job.upload_files(file_paths=[temp_path]):
            raise RuntimeError("Speech-to-text upload failed.")
        job.start()
        job.wait_until_complete(poll_interval=5, timeout=900)
        results = job.get_file_results()
        successful = results.get("successful") or []
        if not successful:
            raise RuntimeError("Speech-to-text returned no successful result.")

        item = successful[0]
        transcript = item.get("transcript", "") if isinstance(item, dict) else ""
        if isinstance(item, dict) and not transcript and item.get("output"):
            output_dir = tempfile.mkdtemp(prefix="collection_stt_")
            job.download_outputs(output_dir)
            for filename in os.listdir(output_dir):
                if filename.endswith(".json"):
                    with open(os.path.join(output_dir, filename), encoding="utf-8") as result_file:
                        payload = json.load(result_file)
                    transcript = payload.get("transcript", "")
                    break
        if not transcript:
            raise RuntimeError("Speech-to-text returned an empty transcript.")
        return transcript.strip()
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass
        if output_dir:
            for filename in os.listdir(output_dir):
                try:
                    os.remove(os.path.join(output_dir, filename))
                except OSError:
                    pass
            try:
                os.rmdir(output_dir)
            except OSError:
                pass


def extract_parameters(transcript):
    text = str(transcript or "").strip()
    if not text:
        raise ValueError("Transcript cannot be empty.")
    # The text extraction API expects the field name "text", not "conversation".
    return post_json(
        configured("TEXT_EXTRACT_URL"),
        configured("TEXT_EXTRACT_API_KEY"),
        {"text": text},
        "Text parameter extraction",
    )


def score_parameters(features):
    return post_json(
        configured("TEXT_SCORE_URL"),
        configured("TEXT_SCORE_API_KEY"),
        features,
        "Text scoring",
    )
