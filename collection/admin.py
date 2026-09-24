from django.contrib import admin

from .models import CollectionSession, ConsentRecord, QuestionnaireResponse


@admin.register(CollectionSession)
class CollectionSessionAdmin(admin.ModelAdmin):
    list_display = ("session_id", "participant_code", "status", "created_at", "consented_at")
    search_fields = ("participant_code", "session_id")


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("patient_id", "gender", "age", "is_minor", "consent_record_date", "created_at")
    search_fields = ("patient_id", "guardian_name", "session__session_id")
    list_filter = ("is_minor", "consent_record_date")
    readonly_fields = ("created_at", "ip_address", "user_agent")


@admin.register(QuestionnaireResponse)
class QuestionnaireResponseAdmin(admin.ModelAdmin):
    list_display = ("session", "submitted_at")
    search_fields = ("session__participant_code", "session__session_id")
