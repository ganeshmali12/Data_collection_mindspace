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
        sound_id = str(instance.metadata.get("sound_id", "unknown"))
        sound_number = re.sub(r"[^0-9]", "", sound_id) or "unknown"
        folder = "voice_phonation"
        name = f"sound_{sound_number.zfill(2)}_{uuid.uuid4().hex[:10]}"
    return f"captures/session_{session_id}/{folder}/{name}{extension}"


class CollectionSession(models.Model):
    STATUS_CHOICES = [
        ("questionnaire", "Questionnaire"),
        ("capture", "Capture"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    participant_code = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="questionnaire")
    current_step = models.CharField(max_length=40, default="questionnaire")
    consented_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.session_id)


class QuestionnaireResponse(models.Model):
    session = models.OneToOneField(CollectionSession, on_delete=models.CASCADE, related_name="questionnaire")
    answers = models.JSONField(default=dict)
    scores = models.JSONField(default=dict)
    flags = models.JSONField(default=list)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Questionnaire for {self.session.session_id}"


class MediaCapture(models.Model):
    KIND_CHOICES = [
        ("combined_video", "Combined face and spoken statement video"),
        ("phonation_audio", "Voice phonation audio"),
    ]
    session = models.ForeignKey(CollectionSession, on_delete=models.CASCADE, related_name="media_captures")
    kind = models.CharField(max_length=40, choices=KIND_CHOICES)
    file = models.FileField(upload_to=media_capture_upload_path)
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, default="uploaded")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.kind} for {self.session.session_id}"


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
    capture = models.ForeignKey(MediaCapture, on_delete=models.SET_NULL, null=True, blank=True, related_name="analysis_results")
    modality = models.CharField(max_length=20, choices=MODALITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    transcript = models.TextField(blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    normalized_result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["session", "modality"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.modality} result for {self.session.session_id}"
