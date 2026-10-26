import json
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import (
    AnalysisResult,
    AnalysisResultCapture,
    CollectionSession,
    ConsentRecord,
    GuardianConsent,
    MediaCapture,
    ParticipantIdentity,
    QuestionnaireResponse,
)


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
        self.assertEqual(consent.participant_email, "")
        self.assertFalse(consent.is_minor)

        # Now accessing questionnaire is allowed
        questionnaire_res = self.client.get("/questionnaire/")
        self.assertEqual(questionnaire_res.status_code, 200)

    def test_consent_with_valid_gmail(self):
        payload = {
            "participant_email": "testuser@gmail.com",
            "gender": "Male",
            "age": 30,
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
        consent = ConsentRecord.objects.filter(participant_email="testuser@gmail.com").first()
        self.assertIsNotNone(consent)
        self.assertTrue(consent.patient_id.startswith("PID-"))

    def test_consent_with_invalid_email_fails(self):
        payload = {
            "participant_email": "testuser@yahoo.com",
            "gender": "Male",
            "age": 30,
            "agree_voice": True,
            "agree_video": True,
            "agree_transcript": True,
            "agree_publication": True,
            "agree_terms": True,
        }
        res = self.client.post("/consent/submit/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("valid Gmail address", res.json()["error"])

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
        self.assertTrue(capture.file.name.endswith(".wav"))

    def test_missing_upload_is_rejected(self):
        response = self.client.post("/screening/combined/upload/")
        self.assertEqual(response.status_code, 400)

    def test_participant_identity_and_guardian_consent_created_properly(self):
        minor_payload = {
            "participant_email": "minoruser@gmail.com",
            "gender": "Female",
            "age": 15,
            "consent_record_date": "2026-09-24",
            "agree_voice": True,
            "agree_video": True,
            "agree_transcript": True,
            "agree_publication": True,
            "agree_terms": True,
            "guardian_name": "Jane Doe",
            "guardian_relationship": "Mother",
            "guardian_contact": "+1234567890",
            "guardian_confirm_parent": True,
            "guardian_confirm_minor": True,
            "guardian_confirm_modalities": True,
            "guardian_confirm_terms": True,
        }
        res = self.client.post("/consent/submit/", data=json.dumps(minor_payload), content_type="application/json")
        self.assertEqual(res.status_code, 200)

        # Verify ParticipantIdentity is created
        identity = ParticipantIdentity.objects.get(participant_email="minoruser@gmail.com")
        self.assertTrue(identity.patient_id.startswith("PID-"))

        # Verify GuardianConsent is created
        guardian = GuardianConsent.objects.get(guardian_name="Jane Doe")
        self.assertEqual(guardian.guardian_relationship, "Mother")
        self.assertEqual(guardian.consent.age, 15)

    def test_media_capture_typed_columns_populated(self):
        # Combined video with duration
        video = SimpleUploadedFile("sample.webm", b"videodata", content_type="video/webm")
        res = self.client.post("/screening/combined/upload/", {"video": video, "duration_seconds": "45.5"})
        self.assertEqual(res.status_code, 200)
        capture = MediaCapture.objects.get(kind="combined_video")
        self.assertEqual(capture.duration_seconds, 45.5)

        # Phonation audio with sound_code and hold_ms
        audio = SimpleUploadedFile("audio.webm", b"audiodata", content_type="audio/webm")
        res2 = self.client.post("/screening/voice/upload/", {"audio": audio, "sound_id": "local-2", "hold_ms": "3000"})
        self.assertEqual(res2.status_code, 200)
        audio_cap = MediaCapture.objects.get(kind="phonation_audio")
        self.assertEqual(audio_cap.sound_code, "local-2")
        self.assertEqual(audio_cap.hold_ms, 3000)

    def test_analysis_result_unique_constraint_enforced(self):
        from django.db import IntegrityError
        session = CollectionSession.objects.create()
        AnalysisResult.objects.create(session=session, modality="face", status="completed")
        with self.assertRaises(IntegrityError):
            AnalysisResult.objects.create(session=session, modality="face", status="pending")

    def test_consent_redirects_to_activity_hub(self):
        payload = {
            "participant_email": "hubuser@gmail.com",
            "gender": "Female",
            "age": 25,
            "consent_record_date": "2026-10-14",
            "agree_voice": True,
            "agree_video": True,
            "agree_transcript": True,
            "agree_publication": True,
            "agree_terms": True,
        }
        res = self.client.post("/consent/submit/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["redirect"], "/activities/")

    def test_unconsented_user_cannot_access_activity_hub(self):
        client = self.client_class()
        res = client.get("/activities/")
        self.assertRedirects(res, "/consent/")

    def test_activity_hub_renders_and_tracks_progress(self):
        # 1. Complete Consent
        payload = {
            "patient_id": "PID-HUB-01",
            "gender": "Male",
            "age": 22,
            "agree_voice": True,
            "agree_video": True,
            "agree_transcript": True,
            "agree_publication": True,
            "agree_terms": True,
        }
        self.client.post("/consent/submit/", data=json.dumps(payload), content_type="application/json")

        # 2. Visit Activity Hub initially (0 of 3 done)
        hub_res = self.client.get("/activities/")
        self.assertEqual(hub_res.status_code, 200)
        self.assertEqual(hub_res.context["completed_count"], 0)
        self.assertFalse(hub_res.context["all_completed"])

        # 3. User chooses Voice Phonation FIRST
        audio = SimpleUploadedFile("audio.webm", b"voice_data", content_type="audio/webm")
        self.client.post("/screening/voice/upload/", {"audio": audio, "sound_id": "local-1", "hold_ms": "3000"})
        hub_res2 = self.client.get("/activities/")
        self.assertTrue(hub_res2.context["voice_done"])
        self.assertFalse(hub_res2.context["questionnaire_done"])
        self.assertFalse(hub_res2.context["combined_done"])
        self.assertEqual(hub_res2.context["completed_count"], 1)

        # 4. User chooses Questionnaire SECOND
        q_payload = {
            "answers": {"1": {"question": "Mood", "value": 0}},
            "scores": {"phq9": 0},
            "flags": [],
        }
        self.client.post("/questionnaire/submit/", data=json.dumps(q_payload), content_type="application/json")
        hub_res3 = self.client.get("/activities/")
        self.assertTrue(hub_res3.context["questionnaire_done"])
        self.assertTrue(hub_res3.context["voice_done"])
        self.assertFalse(hub_res3.context["combined_done"])
        self.assertEqual(hub_res3.context["completed_count"], 2)

        # 5. User chooses Combined Activity THIRD
        video = SimpleUploadedFile("video.webm", b"video_data", content_type="video/webm")
        self.client.post("/screening/combined/upload/", {"video": video, "duration_seconds": "30.0"})
        hub_res4 = self.client.get("/activities/")
        self.assertTrue(hub_res4.context["combined_done"])
        self.assertEqual(hub_res4.context["completed_count"], 3)
        self.assertTrue(hub_res4.context["all_completed"])

    def test_repeat_submissions_same_gmail_unique_pids(self):
        email = "repeatedstudent@gmail.com"
        consent_payload = {
            "participant_email": email,
            "gender": "Female",
            "age": 21,
            "consent_record_date": "2026-10-15",
            "agree_voice": True,
            "agree_video": True,
            "agree_transcript": True,
            "agree_publication": True,
            "agree_terms": True,
        }

        # 1. First submission (Attempt 1)
        res1 = self.client.post("/consent/submit/", data=json.dumps(consent_payload), content_type="application/json")
        self.assertEqual(res1.status_code, 200)
        id1 = ParticipantIdentity.objects.get(participant_email=email)
        self.assertTrue(id1.patient_id.endswith("-01"))

        # 2. Start a new session (e.g. longitudinal follow-up / second record)
        res_new_session = self.client.get("/session/new/")
        self.assertEqual(res_new_session.status_code, 302)
        self.assertEqual(res_new_session.url, "/consent/")

        # 3. Second submission with the SAME Gmail (Attempt 2)
        res2 = self.client.post("/consent/submit/", data=json.dumps(consent_payload), content_type="application/json")
        self.assertEqual(res2.status_code, 200)

        identities = list(ParticipantIdentity.objects.filter(participant_email=email).order_by("created_at"))
        self.assertEqual(len(identities), 2)
        self.assertNotEqual(identities[0].patient_id, identities[1].patient_id)
        self.assertTrue(identities[0].patient_id.endswith("-01"))
        self.assertTrue(identities[1].patient_id.endswith("-02"))
        # Both must share the same base hash prefix (e.g. PID-XXXXXXXX)
        base_hash_1 = identities[0].patient_id.rsplit("-", 1)[0]
        base_hash_2 = identities[1].patient_id.rsplit("-", 1)[0]
        self.assertEqual(base_hash_1, base_hash_2)

        # 4. Third submission with the SAME Gmail (Attempt 3)
        self.client.get("/session/new/")
        res3 = self.client.post("/consent/submit/", data=json.dumps(consent_payload), content_type="application/json")
        self.assertEqual(res3.status_code, 200)

        identities3 = list(ParticipantIdentity.objects.filter(participant_email=email).order_by("created_at"))
        self.assertEqual(len(identities3), 3)
        self.assertTrue(identities3[2].patient_id.endswith("-03"))

    def test_lookup_participant_id_endpoint(self):
        email = "lookuptest@gmail.com"
        # First lookup: new participant
        res = self.client.get(f"/consent/lookup-id/?email={email}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["attempt"], 1)
        self.assertFalse(data["is_repeat"])
        self.assertTrue(data["patient_id"].endswith("-01"))

        # Record consent
        consent_payload = {
            "participant_email": email,
            "gender": "Male",
            "age": 22,
            "consent_record_date": "2026-10-15",
            "agree_voice": True,
            "agree_video": True,
            "agree_transcript": True,
            "agree_publication": True,
            "agree_terms": True,
        }
        self.client.post("/consent/submit/", data=json.dumps(consent_payload), content_type="application/json")

        # Start new session
        self.client.get("/session/new/")

        # Second lookup: repeat participant
        res2 = self.client.get(f"/consent/lookup-id/?email={email}")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertTrue(data2["ok"])
        self.assertEqual(data2["attempt"], 2)
        self.assertTrue(data2["is_repeat"])
        self.assertTrue(data2["patient_id"].endswith("-02"))


