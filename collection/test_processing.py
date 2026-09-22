from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import AnalysisResult, CollectionSession, MediaCapture


class CombinedProcessingTests(TestCase):
    @patch("collection.services.combined_processing.score_features")
    @patch("collection.services.combined_processing.extract_features")
    def test_face_processing_persists_raw_and_normalized_results(self, extract_features, score_features):
        extract_features.return_value = {"features": {"f1": 0.2}}
        score_features.return_value = {"prediction_label": "normal", "confidence_score": 0.9}

        video = SimpleUploadedFile("sample.webm", BytesIO(b"video").read(), content_type="video/webm")
        upload = self.client.post("/screening/combined/upload/", {"video": video})
        capture_id = upload.json()["capture_id"]

        process = self.client.post("/screening/combined/process/", {"capture_id": capture_id})

        self.assertEqual(process.status_code, 200)
        result = AnalysisResult.objects.get(modality="face")
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.normalized_result["prediction_label"], "normal")
        self.assertEqual(CollectionSession.objects.get().current_step, "voice_phonation")
        self.assertEqual(MediaCapture.objects.count(), 1)

    @patch("collection.services.combined_processing.score_parameters")
    @patch("collection.services.combined_processing.extract_parameters")
    @patch("collection.services.combined_processing.score_features")
    @patch("collection.services.combined_processing.extract_features")
    def test_supplied_transcript_is_saved_and_scored(
        self,
        extract_features,
        score_features,
        extract_parameters,
        score_parameters,
    ):
        extract_features.return_value = {"features": {"f1": 0.2}}
        score_features.return_value = {"prediction_label": "normal"}
        extract_parameters.return_value = {"features": {"t1": 0.4}}
        score_parameters.return_value = {"prediction_label": "normal", "confidence_score": 0.8}

        video = SimpleUploadedFile("sample.webm", b"video", content_type="video/webm")
        capture_id = self.client.post("/screening/combined/upload/", {"video": video}).json()["capture_id"]
        response = self.client.post(
            "/screening/combined/process/",
            {"capture_id": capture_id, "transcript": "I feel calm today."},
        )

        self.assertEqual(response.status_code, 200)
        result = AnalysisResult.objects.get(modality="text")
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.transcript, "I feel calm today.")
        self.assertEqual(result.normalized_result["prediction_label"], "normal")
