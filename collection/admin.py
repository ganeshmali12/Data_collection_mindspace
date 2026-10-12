from django.contrib import admin

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


@admin.register(CollectionSession)
class CollectionSessionAdmin(admin.ModelAdmin):
    list_display = ("session_id", "participant_code", "status", "current_step", "is_deleted", "created_at")
    search_fields = ("participant_code", "session_id")
    list_filter = ("status", "current_step", "is_deleted")


@admin.register(ParticipantIdentity)
class ParticipantIdentityAdmin(admin.ModelAdmin):
    list_display = ("patient_id", "participant_email", "ip_address", "created_at")
    search_fields = ("patient_id", "participant_email", "session__session_id")
    readonly_fields = ("created_at", "ip_address", "user_agent")


class GuardianConsentInline(admin.StackedInline):
    model = GuardianConsent
    extra = 0


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("patient_id", "participant_email", "gender", "age", "is_minor", "consent_record_date", "created_at")
    search_fields = ("patient_id", "participant_email", "guardian_name", "session__session_id")
    list_filter = ("is_minor", "consent_record_date")
    readonly_fields = ("created_at", "ip_address", "user_agent")
    inlines = [GuardianConsentInline]


@admin.register(GuardianConsent)
class GuardianConsentAdmin(admin.ModelAdmin):
    list_display = ("guardian_name", "guardian_relationship", "guardian_contact", "consent", "created_at")
    search_fields = ("guardian_name", "guardian_contact", "consent__patient_id")


@admin.register(QuestionnaireResponse)
class QuestionnaireResponseAdmin(admin.ModelAdmin):
    list_display = ("session", "questionnaire_version", "submitted_at")
    search_fields = ("session__participant_code", "session__session_id")
    list_filter = ("questionnaire_version",)


class AnalysisResultCaptureInline(admin.TabularInline):
    model = AnalysisResultCapture
    extra = 0


@admin.register(MediaCapture)
class MediaCaptureAdmin(admin.ModelAdmin):
    list_display = ("session", "kind", "status", "sound_code", "duration_seconds", "hold_ms", "created_at")
    search_fields = ("session__session_id", "sound_code")
    list_filter = ("kind", "status")


@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = ("session", "modality", "status", "risk_score", "started_at", "completed_at")
    search_fields = ("session__session_id", "modality")
    list_filter = ("modality", "status")
    inlines = [AnalysisResultCaptureInline]


@admin.register(AnalysisResultCapture)
class AnalysisResultCaptureAdmin(admin.ModelAdmin):
    list_display = ("analysis_result", "capture", "role", "created_at")
    search_fields = ("analysis_result__session__session_id", "role")
