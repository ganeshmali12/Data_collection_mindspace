from django.urls import path

from . import views

app_name = "collection"

urlpatterns = [
    path("", views.home, name="home"),
    path("questionnaire/", views.questionnaire, name="questionnaire"),
    path("questionnaire/submit/", views.submit_questionnaire, name="submit_questionnaire"),
    path("screening/combined/", views.combined_activity, name="combined_activity"),
    path("screening/combined/upload/", views.upload_combined_video, name="upload_combined_video"),
    path("screening/combined/process/", views.process_combined_video, name="process_combined_video"),
    path("screening/status/", views.screening_status, name="screening_status"),
    path("screening/voice/", views.voice_phonation, name="voice_phonation"),
    path("screening/voice/sounds/", views.phonation_sound_config, name="phonation_sound_config"),
    path("screening/voice/upload/", views.upload_voice_phonation, name="upload_voice_phonation"),
    path("screening/voice/complete/", views.complete_voice_phonation, name="complete_voice_phonation"),
    path("screening/fusion/", views.process_fusion, name="process_fusion"),
    path("screening/completed/", views.completed, name="completed"),
    path("health/", views.health, name="health"),
]
