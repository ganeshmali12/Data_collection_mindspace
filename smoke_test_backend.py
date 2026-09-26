import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import json
from unittest.mock import patch
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from collection.models import CollectionSession, ConsentRecord, MediaCapture, QuestionnaireResponse

def run_smoke_test():
    print("=======================================================")
    print("       STARTING FULL BACKEND SMOKE TEST SUITE          ")
    print("=======================================================")
    client = Client()

    # 1. Health check
    res = client.get("/health/")
    assert res.status_code == 200, f"Health check failed: {res.status_code}"
    print("[PASS]  1. GET  /health/                     -> 200 OK")

    # 2. Home redirects to consent
    res = client.get("/")
    assert res.status_code in [301, 302], f"Home redirect failed: {res.status_code}"
    print("[PASS]  2. GET  /                            -> 302 Redirect to /consent/")

    # 3. Consent page loads
    res = client.get("/consent/")
    assert res.status_code == 200, f"Consent GET failed: {res.status_code}"
    print("[PASS]  3. GET  /consent/                    -> 200 OK")

    # 4. Consent submission
    consent_payload = {
        "patient_id": "SMOKE-TEST-01",
        "gender": "Female",
        "age": 29,
        "consent_record_date": "2026-09-24",
        "agree_voice": True,
        "agree_video": True,
        "agree_transcript": True,
        "agree_publication": True,
        "agree_terms": True,
    }
    res = client.post("/consent/submit/", data=json.dumps(consent_payload), content_type="application/json")
    assert res.status_code == 200, f"Consent POST failed: {res.status_code}, {res.content}"
    data = res.json()
    assert data.get("ok") is True, f"Consent response not OK: {data}"
    print("[PASS]  4. POST /consent/submit/             -> 200 OK (Consent stored)")

    # 5. Questionnaire page loads
    res = client.get("/questionnaire/")
    assert res.status_code == 200, f"Questionnaire GET failed: {res.status_code}"
    print("[PASS]  5. GET  /questionnaire/              -> 200 OK")

    # 6. Questionnaire submission
    q_payload = {
        "answers": {"1": {"value": 0}, "2": {"value": 1}},
        "scores": {"phq9": 1},
        "flags": [],
    }
    res = client.post("/questionnaire/submit/", data=json.dumps(q_payload), content_type="application/json")
    assert res.status_code == 200, f"Questionnaire POST failed: {res.status_code}"
    assert res.json().get("ok") is True
    print("[PASS]  6. POST /questionnaire/submit/       -> 200 OK (PHQ-9 saved)")

    # 7. Combined activity page loads
    res = client.get("/screening/combined/")
    assert res.status_code == 200, f"Combined activity GET failed: {res.status_code}"
    assert "story-frames-data" in res.content.decode() or "Observe &amp; Describe" in res.content.decode()
    print("[PASS]  7. GET  /screening/combined/         -> 200 OK (Story frames ready)")

    # 8. Combined video upload
    sample_video = SimpleUploadedFile("combined.webm", b"fake_webm_video_data", content_type="video/webm")
    res = client.post("/screening/combined/upload/", {
        "video": sample_video,
        "duration_seconds": "45",
        "activity_id": "combined_observe_describe",
        "activity_title": "Combined Observe & Describe",
        "activity_prompt": "Prompt 1 Prompt 2 Prompt 3 Prompt 4"
    })
    assert res.status_code == 200, f"Combined upload failed: {res.status_code}, {res.content}"
    upload_data = res.json()
    assert upload_data.get("ok") is True
    capture_id = upload_data.get("capture_id")
    assert capture_id is not None
    print(f"[PASS]  8. POST /screening/combined/upload/  -> 200 OK (Capture ID: {capture_id})")

    # 9. Combined video process endpoint
    with patch("collection.views.process_combined_capture") as mock_proc:
        mock_proc.return_value = None
        res = client.post("/screening/combined/process/", {"capture_id": capture_id})
        assert res.status_code == 200, f"Combined process failed: {res.status_code}"
        assert res.json().get("ok") is True
        print("[PASS]  9. POST /screening/combined/process/ -> 200 OK")

    # 10. Voice phonation page loads
    res = client.get("/screening/voice/")
    assert res.status_code == 200, f"Voice phonation GET failed: {res.status_code}"
    print("[PASS] 10. GET  /screening/voice/            -> 200 OK")

    # 11. Phonation sounds config
    res = client.get("/screening/voice/sounds/")
    assert res.status_code == 200, f"Voice sounds GET failed: {res.status_code}"
    sounds_data = res.json()
    assert sounds_data.get("ok") is True
    assert len(sounds_data.get("sounds", [])) > 0
    print(f"[PASS] 11. GET  /screening/voice/sounds/     -> 200 OK ({len(sounds_data['sounds'])} sounds configured)")

    # 12. Phonation audio upload
    sample_audio = SimpleUploadedFile("phonation.webm", b"fake_phonation_audio_data", content_type="audio/webm")
    res = client.post("/screening/voice/upload/", {
        "audio": sample_audio,
        "sound_id": "local-1",
        "hold_ms": "950"
    })
    assert res.status_code == 200, f"Voice upload failed: {res.status_code}, {res.content}"
    assert res.json().get("ok") is True
    print("[PASS] 12. POST /screening/voice/upload/     -> 200 OK")

    # 13. Phonation completion
    with patch("collection.views.process_voice_session") as mock_voice, patch("collection.views.process_fusion_session") as mock_fusion:
        mock_voice.return_value = None
        mock_fusion.return_value = None
        res = client.post("/screening/voice/complete/")
        assert res.status_code == 200, f"Voice complete failed: {res.status_code}"
        assert res.json().get("ok") is True
        print("[PASS] 13. POST /screening/voice/complete/   -> 200 OK")

    # 14. Screening status
    res = client.get("/screening/status/")
    assert res.status_code == 200, f"Screening status GET failed: {res.status_code}"
    assert res.json().get("ok") is True
    print("[PASS] 14. GET  /screening/status/           -> 200 OK")

    # 15. Completed page loads
    res = client.get("/screening/completed/")
    assert res.status_code == 200, f"Screening completed GET failed: {res.status_code}"
    print("[PASS] 15. GET  /screening/completed/        -> 200 OK")

    print("\n=======================================================")
    print("ALL 15 BACKEND ENDPOINTS PASSED SMOKE TEST SUCCESSFULLY!")
    print("=======================================================")

if __name__ == "__main__":
    run_smoke_test()
