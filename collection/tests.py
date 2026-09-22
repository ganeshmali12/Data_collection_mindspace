import json
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import CollectionSession, MediaCapture, QuestionnaireResponse


class CollectionFlowTests(TestCase):
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
