from django.contrib import admin

from .models import CollectionSession, QuestionnaireResponse


@admin.register(CollectionSession)
class CollectionSessionAdmin(admin.ModelAdmin):
    list_display = ("session_id", "participant_code", "created_at", "consented_at")
    search_fields = ("participant_code", "session_id")


@admin.register(QuestionnaireResponse)
class QuestionnaireResponseAdmin(admin.ModelAdmin):
    list_display = ("session", "submitted_at")
    search_fields = ("session__participant_code", "session__session_id")
