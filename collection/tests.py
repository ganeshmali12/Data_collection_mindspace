import json
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import CollectionSession, ConsentRecord, MediaCapture, QuestionnaireResponse


class ConsentFlowTests(TestCase):
    def test_unconsented_user_is_redirected_to_consent(self):
        response = self.client.get("/questionnaire/")
        self.assertRedirects(response, "/consent/")

    def test_home_redirects_to_consent_initially(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/consent/")

    def test_adult_consent_submission_and_access(self):
        payload = {
            "patient_id": "PID-101",
            "gender": "Female",
            "age": 28,
            "consent_record_date": "2026-09-24",
            "agree_voice": True,
            "agree_video": True,
            "agree_transcript": True,
            "agree_publication": True,
            "agree_terms": True,
        }
        res = self.client.post("/consent/submit/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])

        # Consent record created
        self.assertEqual(ConsentRecord.objects.count(), 1)
        consent = ConsentRecord.objects.first()
        self.assertEqual(consent.patient_id, "PID-101")
        self.assertFalse(consent.is_minor)

        # Now accessing questionnaire is allowed
        questionnaire_res = self.client.get("/questionnaire/")
        self.assertEqual(questionnaire_res.status_code, 200)

    def test_minor_consent_requires_guardian_details(self):
        payload = {
            "patient_id": "PID-MINOR-01",
            "gender": "Male",
            "age": 15,
            "agree_voice": True,
            "agree_video": True,
            "agree_transcript": True,
            "agree_publication": True,
            "agree_terms": True,
        }
        res = self.client.post("/consent/submit/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Section H2", res.json()["error"])

    def test_minor_consent_with_guardian_details_succeeds(self):
        payload = {
            "patient_id": "PID-MINOR-01",
            "gender": "Male",
            "age": 15,
            "consent_record_date": "2026-09-24",
            "agree_voice": True,
            "agree_video": True,
            "agree_transcript": True,
            "agree_publication": True,
            "agree_terms": True,
            "guardian_name": "Jane Doe",
            "guardian_relationship": "Mother",
            "guardian_contact": "+91 9999988888",
            "guardian_confirm_parent": True,
            "guardian_confirm_minor": True,
            "guardian_confirm_modalities": True,
            "guardian_confirm_terms": True,
        }
        res = self.client.post("/consent/submit/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 200)
        consent = ConsentRecord.objects.first()
        self.assertTrue(consent.is_minor)
        self.assertEqual(consent.guardian_name, "Jane Doe")


class CollectionFlowTests(TestCase):
    def setUp(self):
        # Establish consent first for session
        self.client.post(
            "/consent/submit/",
            data=json.dumps({
                "patient_id": "PID-TEST",
                "gender": "Male",
                "age": 25,
                "consent_record_date": "2026-09-24",
                "agree_voice": True,
                "agree_video": True,
                "agree_transcript": True,
                "agree_publication": True,
                "agree_terms": True,
            }),
            content_type="application/json",
        )

    def test_questionnaire_and_video_share_one_collection_session(self):
        questionnaire_response = self.client.post(
            "/questionnaire/submit/",
            data=json.dumps({
                "answers": {"1": {"value": 0}},
                "scores": {"phq9": 0},
                "flags": [],
            }),
            content_type="application/json",
        )
        self.assertEqual(questionnaire_response.status_code, 200)

        video = SimpleUploadedFile("sample.webm", BytesIO(b"video").read(), content_type="video/webm")
        upload_response = self.client.post(
            "/screening/combined/upload/",
            {"video": video, "duration_seconds": "120"},
        )
        self.assertEqual(upload_response.status_code, 200)

        self.assertEqual(CollectionSession.objects.count(), 1)
        session = CollectionSession.objects.get()
        self.assertEqual(session.current_step, "face_text_processing")
        self.assertEqual(QuestionnaireResponse.objects.get().session_id, session.pk)
        capture = MediaCapture.objects.get()
        self.assertEqual(capture.session_id, session.pk)
        self.assertIn(f"session_{session.session_id}/combined_video/", capture.file.name)

    def test_voice_capture_path_identifies_sound_and_session(self):
        response = self.client.post(
            "/screening/voice/upload/",
            {"audio": SimpleUploadedFile("browser-name.webm", b"audio", content_type="audio/webm"), "sound_id": "local-3"},
        )
        self.assertEqual(response.status_code, 200)
        capture = MediaCapture.objects.get()
        self.assertIn(f"session_{capture.session.session_id}/voice_phonation/sound_03_", capture.file.name)

    def test_missing_upload_is_rejected(self):
        response = self.client.post("/screening/combined/upload/")
        self.assertEqual(response.status_code, 400)
