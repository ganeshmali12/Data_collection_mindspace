import os
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import AnalysisResult, CollectionSession, MediaCapture


class VoiceProcessingTests(TestCase):
    @patch("collection.views.process_fusion_session")
    @patch("collection.services.voice_processing.score_features")
    @patch("collection.services.voice_processing.process_pca")
    @patch("collection.services.voice_processing.extract_features")
    @patch("collection.services.voice_processing.combine_audio")
    def test_seven_captures_produce_voice_result(
        self,
        combine_audio,
        extract_features,
        process_pca,
        score_features,
        process_fusion,
    ):
        combined = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        combined.write(b"wav")
        combined.close()
        combine_audio.return_value = combined.name
        extract_features.return_value = {"features": {"f1": 0.2}}
        process_pca.return_value = {"components": {"PC1": 0.4}}
        score_features.return_value = {"prediction_label": "normal", "confidence_score": 0.9}
        process_fusion.return_value = None

        session = CollectionSession.objects.create()
        client_session = self.client.session
        client_session["collection_session_id"] = str(session.session_id)
        client_session.save()
        for index in range(7):
            capture = SimpleUploadedFile(f"sound-{index}.webm", b"audio", content_type="audio/webm")
            MediaCapture.objects.create(session=session, kind="phonation_audio", file=capture)

        response = self.client.post("/screening/voice/complete/")

        self.assertEqual(response.status_code, 200)
        result = AnalysisResult.objects.get(session=session, modality="voice")
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.normalized_result["prediction_label"], "normal")
        session.refresh_from_db()
        self.assertEqual(session.current_step, "multimodal_processing")
        self.assertFalse(os.path.exists(combined.name))
