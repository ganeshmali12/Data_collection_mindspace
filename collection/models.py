import uuid
from pathlib import Path
import re

from django.db import models


def media_capture_upload_path(instance, filename):
    extension = Path(filename).suffix.lower() or ".webm"
    session_id = str(instance.session.session_id)
    if instance.kind == "combined_video":
        folder = "combined_video"
        name = f"combined_video_{uuid.uuid4().hex[:10]}"
    else:
        sound_id = str(getattr(instance, "sound_code", "") or instance.metadata.get("sound_id", "unknown"))
        sound_number = re.sub(r"[^0-9]", "", sound_id) or "unknown"
        folder = "voice_phonation"
        name = f"sound_{sound_number.zfill(2)}_{uuid.uuid4().hex[:10]}"
    return f"captures/session_{session_id}/{folder}/{name}{extension}"


class CollectionSession(models.Model):
    STATUS_CHOICES = [
        ("consent", "Consent"),
        ("questionnaire", "Questionnaire"),
        ("capture", "Capture"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    CURRENT_STEP_CHOICES = [
        ("consent", "Consent"),
        ("questionnaire", "Questionnaire"),
        ("combined_video", "Combined Video Capture"),
        ("face_text_processing", "Face & Text Processing"),
        ("voice_phonation", "Voice Phonation"),
        ("multimodal_processing", "Multimodal Processing"),
        ("completed", "Completed"),
        ("voice_processing_failed", "Voice Processing Failed"),
    ]
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    participant_code = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="consent")
    current_step = models.CharField(max_length=40, choices=CURRENT_STEP_CHOICES, default="consent")
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    consented_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.session_id)


class ParticipantIdentity(models.Model):
    """
    Stores sensitive identifying data (PII) separately from clinical records.
    Allows independent data erasure (GDPR/DPDP right-to-erasure compliance)
    without corrupting anonymized research dataset integrity.
    """
    session = models.OneToOneField(CollectionSession, on_delete=models.CASCADE, related_name="identity")
    patient_id = models.CharField(max_length=100, unique=True)
    participant_email = models.EmailField(max_length=254, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Identity {self.patient_id} for session {self.session.session_id}"


class ConsentRecord(models.Model):
    session = models.OneToOneField(CollectionSession, on_delete=models.CASCADE, related_name="consent")
    patient_id = models.CharField(max_length=100)
    participant_email = models.EmailField(max_length=254, blank=True)
    gender = models.CharField(max_length=30)
    age = models.PositiveIntegerField()
    consent_record_date = models.DateField()
    agree_voice = models.BooleanField(default=False)
    agree_video = models.BooleanField(default=False)
    agree_transcript = models.BooleanField(default=False)
    agree_publication = models.BooleanField(default=False)
    agree_terms = models.BooleanField(default=False)
    is_minor = models.BooleanField(default=False)
    guardian_name = models.CharField(max_length=200, blank=True)
    guardian_relationship = models.CharField(max_length=100, blank=True)
    guardian_contact = models.CharField(max_length=100, blank=True)
    guardian_confirm_parent = models.BooleanField(default=False)
    guardian_confirm_minor = models.BooleanField(default=False)
    guardian_confirm_modalities = models.BooleanField(default=False)
    guardian_confirm_terms = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(age__gt=0) & models.Q(age__lte=130),
                name="valid_age_range",
            )
        ]

    def __str__(self):
        return f"Consent for {self.patient_id} ({self.session.session_id})"


class GuardianConsent(models.Model):
    """
    Normalized guardian consent record for minor participants (age < 18).
    Separates 3NF sparse columns out of general ConsentRecord.
    """
    consent = models.OneToOneField(ConsentRecord, on_delete=models.CASCADE, related_name="guardian")
    guardian_name = models.CharField(max_length=200)
    guardian_relationship = models.CharField(max_length=100)
    guardian_contact = models.CharField(max_length=100)
    confirm_parent = models.BooleanField(default=False)
    confirm_minor = models.BooleanField(default=False)
    confirm_modalities = models.BooleanField(default=False)
    confirm_terms = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Guardian {self.guardian_name} for Consent {self.consent.patient_id}"


class QuestionnaireResponse(models.Model):
    session = models.OneToOneField(CollectionSession, on_delete=models.CASCADE, related_name="questionnaire")
    questionnaire_version = models.CharField(max_length=20, default="v1")
    answers = models.JSONField(default=dict)
    scores = models.JSONField(default=dict)
    flags = models.JSONField(default=list)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Questionnaire ({self.questionnaire_version}) for {self.session.session_id}"


class MediaCapture(models.Model):
    KIND_CHOICES = [
        ("combined_video", "Combined face and spoken statement video"),
        ("phonation_audio", "Voice phonation audio"),
    ]
    STATUS_CHOICES = [
        ("uploaded", "Uploaded"),
        ("processing", "Processing"),
        ("processed", "Processed"),
        ("failed", "Failed"),
    ]
    session = models.ForeignKey(CollectionSession, on_delete=models.CASCADE, related_name="media_captures")
    kind = models.CharField(max_length=40, choices=KIND_CHOICES)
    file = models.FileField(upload_to=media_capture_upload_path)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="uploaded")
    sound_code = models.CharField(max_length=20, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    hold_ms = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.kind} ({self.status}) for {self.session.session_id}"


class AnalysisResultCapture(models.Model):
    """
    Many-to-Many through entity linking MediaCapture records to AnalysisResults.
    Maintains full data provenance and audit lineage for multi-clip analysis
    (e.g. 7 phonation sounds feeding a single voice analysis).
    """
    analysis_result = models.ForeignKey("AnalysisResult", on_delete=models.CASCADE, related_name="capture_links")
    capture = models.ForeignKey(MediaCapture, on_delete=models.CASCADE, related_name="result_links")
    role = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("analysis_result", "capture")]

    def __str__(self):
        return f"Capture {self.capture_id} -> Result {self.analysis_result_id} ({self.role})"


class AnalysisResult(models.Model):
    MODALITY_CHOICES = [
        ("face", "Face"),
        ("text", "Text"),
        ("voice", "Voice"),
        ("multimodal", "Multimodal"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    session = models.ForeignKey(CollectionSession, on_delete=models.CASCADE, related_name="analysis_results")
    capture = models.ForeignKey(
        MediaCapture,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_analysis_results",
    )
    captures = models.ManyToManyField(
        MediaCapture,
        through=AnalysisResultCapture,
        related_name="analysis_results",
    )
    modality = models.CharField(max_length=20, choices=MODALITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    risk_score = models.FloatField(null=True, blank=True)
    transcript = models.TextField(blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    normalized_result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "modality"],
                name="unique_session_modality",
            )
        ]
        indexes = [
            models.Index(fields=["session", "modality"]),
            models.Index(fields=["status"]),
            models.Index(fields=["risk_score"]),
        ]

    def __str__(self):
        return f"{self.modality} result for {self.session.session_id}"
