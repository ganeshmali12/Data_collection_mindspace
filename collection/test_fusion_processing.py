from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .models import AnalysisResult, CollectionSession, ConsentRecord


class FusionProcessingTests(TestCase):
    @patch("collection.services.fusion_processing.score_fusion")
    def test_fusion_requires_three_results_and_completes_session(self, score_fusion):
        score_fusion.return_value = {"prediction_label": "normal", "confidence_score": 0.88}
        session = CollectionSession.objects.create(consented_at=timezone.now())
        ConsentRecord.objects.create(
            session=session,
            patient_id="PID-FUSION",
            gender="Other",
            age=22,
            consent_record_date="2026-09-24",
            agree_voice=True,
            agree_video=True,
            agree_transcript=True,
            agree_publication=True,
            agree_terms=True,
        )
        for modality, payload in [
            ("face", {"extraction": {"features": {"blink_rate": 0.2}}}),
            ("text", {"extraction": {"features": {"negative_frequency": 0.1}}}),
            ("voice", {"pca": {"components": {"PC1": 0.3}}}),
        ]:
            AnalysisResult.objects.create(
                session=session,
                modality=modality,
                status="completed",
                raw_response=payload,
            )

        client_session = self.client.session
        client_session["collection_session_id"] = str(session.session_id)
        client_session.save()
        response = self.client.post("/screening/fusion/")

        self.assertEqual(response.status_code, 200)
        fusion = AnalysisResult.objects.get(session=session, modality="multimodal")
        self.assertEqual(fusion.status, "completed")
        self.assertEqual(fusion.normalized_result["prediction_label"], "normal")
        session.refresh_from_db()
        self.assertEqual(session.status, "completed")
        self.assertEqual(session.current_step, "completed")