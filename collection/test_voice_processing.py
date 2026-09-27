import os
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from .models import AnalysisResult, CollectionSession, ConsentRecord, MediaCapture


class VoiceProcessingTests(TestCase):
    @patch("collection.views.process_fusion_session")
    @patch("collection.services.voice_processing.score_features")
    @patch("collection.services.voice_processing.process_pca")
    @patch("collection.services.voice_processing.extract_features")
    @patch("collection.services.voice_processing.clean_audio_file")
    def test_single_capture_produces_voice_result(
        self,
        clean_audio_file,
        extract_features,
        process_pca,
        score_features,
        process_fusion,
    ):
        cleaned = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        cleaned.write(b"wav")
        cleaned.close()
        clean_audio_file.return_value = cleaned.name
        extract_features.return_value = {"features": {"f1": 0.2}}
        process_pca.return_value = {"components": {"PC1": 0.4}}
        score_features.return_value = {"prediction_label": "normal", "confidence_score": 0.9}
        process_fusion.return_value = None

        session = CollectionSession.objects.create(consented_at=timezone.now())
        ConsentRecord.objects.create(
            session=session,
            patient_id="PID-VOICE-SINGLE",
            gender="Female",
            age=30,
            consent_record_date="2026-09-24",
            agree_voice=True,
            agree_video=True,
            agree_transcript=True,
            agree_publication=True,
            agree_terms=True,
        )
        client_session = self.client.session
        client_session["collection_session_id"] = str(session.session_id)
        client_session.save()

        # Upload 1 single consolidated audio capture
        audio_file = SimpleUploadedFile("phonation_session_master.webm", b"audio_master", content_type="audio/webm")
        upload_resp = self.client.post("/screening/voice/upload/", {"audio": audio_file, "sound_id": "session-master"})
        self.assertEqual(upload_resp.status_code, 200)

        response = self.client.post("/screening/voice/complete/")
        self.assertEqual(response.status_code, 200)

        result = AnalysisResult.objects.get(session=session, modality="voice")
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.normalized_result["prediction_label"], "normal")
        session.refresh_from_db()
        self.assertEqual(session.current_step, "multimodal_processing")
        self.assertFalse(os.path.exists(cleaned.name))
