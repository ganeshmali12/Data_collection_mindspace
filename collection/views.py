import hashlib
import json
import random
import threading
from pathlib import Path

import datetime
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import CollectionSession, ConsentRecord, MediaCapture, QuestionnaireResponse
from .services.combined_processing import process_combined_capture
from .services.voice_processing import process_voice_session
from .services.fusion_processing import process_fusion_session


STORY_IMAGE_DIR = Path(__file__).resolve().parent.parent / "static" / "images" / "activities" / "story"


def generate_participant_id_from_email(email: str) -> str:
    """Derive a stable, short, opaque Participant ID from a Gmail address.

    Format: PID-XXXXXXXX  (8 uppercase hex chars)
    The raw email is NOT encoded in the ID — only a SHA-256 hash is used,
    making it safe to display publicly while remaining deterministic.
    """
    normalized = email.strip().lower()
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:8].upper()
    return f"PID-{digest}"


def pick_story_frames():
    story_sets = sorted(path for path in STORY_IMAGE_DIR.glob("set-*") if path.is_dir())
    if not story_sets:
        return []
    chosen_set = random.choice(story_sets)
    frame_files = sorted(
        (path for path in chosen_set.iterdir() if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}),
        key=lambda path: (len(path.stem), path.stem),
    )[:4]
    return [
        f"/static/images/activities/story/{chosen_set.name}/{frame.name}"
        for frame in frame_files
    ]


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def home(request):
    session_id = request.session.get("collection_session_id")
    if session_id and CollectionSession.objects.filter(
        session_id=session_id,
        consented_at__isnull=False,
        consent__isnull=False,
    ).exists():
        return redirect("collection:questionnaire")
    return redirect("collection:consent")


def get_collection_session(request):
    session_id = request.session.get("collection_session_id")
    session = CollectionSession.objects.filter(session_id=session_id).first() if session_id else None
    if not session:
        session = CollectionSession.objects.create()
        request.session["collection_session_id"] = str(session.session_id)
    return session


@ensure_csrf_cookie
def consent_view(request):
    session = get_collection_session(request)
    existing_consent = getattr(session, "consent", None)
    return render(request, "collection/consent.html", {
        "session": session,
        "existing_consent": existing_consent,
        "today": timezone.now().date().isoformat(),
    })


@require_POST
def submit_consent(request):
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({"ok": False, "error": "Invalid JSON payload."}, status=400)
    else:
        data = request.POST.dict()

    participant_email = str(data.get("participant_email", "")).strip().lower()

    # Validate that a proper Gmail address was provided
    if not participant_email:
        return JsonResponse({"ok": False, "error": "A Gmail address is required."}, status=400)
    if not participant_email.endswith("@gmail.com"):
        return JsonResponse({"ok": False, "error": "Please enter a valid Gmail address (must end with @gmail.com)."}, status=400)

    # Auto-generate the Participant ID server-side from the Gmail (client value is never trusted)
    patient_id = generate_participant_id_from_email(participant_email)

    gender = str(data.get("gender", "")).strip()
    age_raw = data.get("age")
    consent_date_raw = data.get("consent_record_date", "")

    if not gender:
        return JsonResponse({"ok": False, "error": "Gender selection is required."}, status=400)
    try:
        age = int(age_raw)
        if age <= 0 or age > 130:
            raise ValueError()
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "A valid age is required."}, status=400)

    try:
        if consent_date_raw:
            consent_date = datetime.date.fromisoformat(str(consent_date_raw).strip())
        else:
            consent_date = timezone.now().date()
    except ValueError:
        consent_date = timezone.now().date()

    def to_bool(val):
        return str(val).lower() in {"true", "1", "yes", "on"}

    agree_voice = to_bool(data.get("agree_voice"))
    agree_video = to_bool(data.get("agree_video"))
    agree_transcript = to_bool(data.get("agree_transcript"))
    agree_publication = to_bool(data.get("agree_publication"))
    agree_terms = to_bool(data.get("agree_terms"))

    if not (agree_voice and agree_video and agree_transcript and agree_publication and agree_terms):
        return JsonResponse({
            "ok": False,
            "error": "All declaration checkboxes in Section H must be accepted to participate.",
        }, status=400)

    is_minor = age < 18
    guardian_name = ""
    guardian_relationship = ""
    guardian_contact = ""
    guardian_confirm_parent = False
    guardian_confirm_minor = False
    guardian_confirm_modalities = False
    guardian_confirm_terms = False

    if is_minor:
        guardian_name = str(data.get("guardian_name", "")).strip()
        guardian_relationship = str(data.get("guardian_relationship", "")).strip()
        guardian_contact = str(data.get("guardian_contact", "")).strip()
        guardian_confirm_parent = to_bool(data.get("guardian_confirm_parent"))
        guardian_confirm_minor = to_bool(data.get("guardian_confirm_minor"))
        guardian_confirm_modalities = to_bool(data.get("guardian_confirm_modalities"))
        guardian_confirm_terms = to_bool(data.get("guardian_confirm_terms"))

        if not guardian_name or not guardian_relationship or not guardian_contact:
            return JsonResponse({
                "ok": False,
                "error": "For participants below 18 years, all parent/guardian fields in Section H2 are mandatory.",
            }, status=400)

        if not (guardian_confirm_parent and guardian_confirm_minor and guardian_confirm_modalities and guardian_confirm_terms):
            return JsonResponse({
                "ok": False,
                "error": "For participants below 18 years, all parent/guardian confirmation checkboxes in Section H2 must be checked.",
            }, status=400)

    session = get_collection_session(request)
    session.participant_code = patient_id
    session.consented_at = timezone.now()
    if session.status == "consent":
        session.status = "questionnaire"
    if session.current_step == "consent":
        session.current_step = "questionnaire"
    session.save(update_fields=["participant_code", "consented_at", "status", "current_step", "updated_at"])

    ip_address = get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]

    ConsentRecord.objects.update_or_create(
        session=session,
        defaults={
            "patient_id": patient_id,
            "participant_email": participant_email,
            "gender": gender,
            "age": age,
            "consent_record_date": consent_date,
            "agree_voice": agree_voice,
            "agree_video": agree_video,
            "agree_transcript": agree_transcript,
            "agree_publication": agree_publication,
            "agree_terms": agree_terms,
            "is_minor": is_minor,
            "guardian_name": guardian_name,
            "guardian_relationship": guardian_relationship,
            "guardian_contact": guardian_contact,
            "guardian_confirm_parent": guardian_confirm_parent,
            "guardian_confirm_minor": guardian_confirm_minor,
            "guardian_confirm_modalities": guardian_confirm_modalities,
            "guardian_confirm_terms": guardian_confirm_terms,
            "ip_address": ip_address,
            "user_agent": user_agent,
        },
    )

    return JsonResponse({
        "ok": True,
        "message": "Consent recorded successfully.",
        "redirect": reverse("collection:questionnaire"),
    })


@ensure_csrf_cookie
def questionnaire(request):
    return render(request, "collection/questionnaire.html")


def combined_activity(request):
    return render(request, "collection/combined_activity.html", {
        "session": get_collection_session(request),
        "story_frames": pick_story_frames(),
    })


@require_POST
def upload_combined_video(request):
    video = request.FILES.get("video")
    if not video:
        return JsonResponse({"ok": False, "error": "No video received."}, status=400)
    capture = MediaCapture.objects.create(
        session=get_collection_session(request), kind="combined_video", file=video,
        metadata={"duration_seconds": request.POST.get("duration_seconds", "")},
    )
    session = capture.session
    session.status = "processing"
    session.current_step = "face_text_processing"
    session.save(update_fields=["status", "current_step", "updated_at"])
    return JsonResponse({"ok": True, "capture_id": capture.pk, "message": "Video saved for processing."})


@require_POST
def process_combined_video(request):
    capture_id = request.POST.get("capture_id")
    transcript = request.POST.get("transcript", "")
    if not capture_id:
        return JsonResponse({"ok": False, "error": "capture_id is required."}, status=400)
    try:
        session = get_collection_session(request)
        capture = MediaCapture.objects.get(pk=capture_id, session=session, kind="combined_video")
        
        # Run heavy processing in background thread so the client transitions instantly
        thread = threading.Thread(
            target=process_combined_capture,
            args=(capture.pk,),
            kwargs={"transcript": transcript},
            daemon=True,
        )
        thread.start()
    except MediaCapture.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Capture not found."}, status=404)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)
    return JsonResponse({"ok": True, "message": "Face and text processing started."})


def screening_status(request):
    session = get_collection_session(request)
    results = session.analysis_results.order_by("modality")
    voice_done = session.analysis_results.filter(modality="voice", status="completed").exists()
    fusion_done = session.analysis_results.filter(modality="multimodal", status="completed").exists()
    return JsonResponse({
        "ok": True,
        "session_id": str(session.session_id),
        "status": session.status,
        "current_step": session.current_step,
        "voice_done": voice_done,
        "fusion_done": fusion_done,
        "results": [
            {"modality": result.modality, "status": result.status, "error": result.error_message}
            for result in results
        ],
    })


def voice_phonation(request):
    return render(request, "collection/voice_phonation.html")


def phonation_sound_config(request):
    sounds = [
        {"sound_id": f"local-{index}", "label": label, "prompt": label, "say": label,
         "help": "Hold the sound steadily until the circle completes.", "order": index,
         "required_hold_ms": 750, "voice_threshold": 15, "accepted": []}
        for index, label in enumerate(["आ", "ई", "ऊ", "ए", "ओ", "अ", "म्"], start=1)
    ]
    return JsonResponse({"ok": True, "sounds": sounds})


@require_POST
def upload_voice_phonation(request):
    audio = request.FILES.get("audio")
    if not audio:
        return JsonResponse({"ok": False, "error": "No audio received."}, status=400)
    capture = MediaCapture.objects.create(
        session=get_collection_session(request), kind="phonation_audio", file=audio,
        metadata={"sound_id": request.POST.get("sound_id", ""), "hold_ms": request.POST.get("hold_ms", "")},
    )
    return JsonResponse({"ok": True, "capture_id": capture.pk, "passed": True})


@require_POST
def complete_voice_phonation(request):
    session = get_collection_session(request)
    try:
        process_voice_session(session)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": f"Voice analysis failed: {str(exc)}"}, status=502)

    try:
        process_fusion_session(session)
    except Exception:
        pass

    return JsonResponse({"ok": True, "message": "Voice analysis completed."})


@require_POST
def process_fusion(request):
    session = get_collection_session(request)
    try:
        process_fusion_session(session)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)
    return JsonResponse({"ok": True, "message": "Multimodal result saved."})


def completed(request):
    return render(request, "collection/completed.html")


@require_POST
def submit_questionnaire(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "Invalid questionnaire payload."}, status=400)

    answers = payload.get("answers")
    scores = payload.get("scores")
    flags = payload.get("flags", [])
    if not isinstance(answers, dict) or not isinstance(scores, dict) or not isinstance(flags, list):
        return JsonResponse({"ok": False, "error": "Questionnaire data has an invalid shape."}, status=400)

    session = get_collection_session(request)
    session.participant_code = str(payload.get("participant_code", "")).strip()
    session.status = "capture"
    session.current_step = "combined_video"
    session.save(update_fields=["participant_code", "status", "current_step", "updated_at"])
    response, _ = QuestionnaireResponse.objects.update_or_create(
        session=session,
        defaults={"answers": answers, "scores": scores, "flags": flags},
    )
    return JsonResponse({"ok": True, "session_id": str(session.session_id), "response_id": response.pk})


def health(request):
    return JsonResponse({"ok": True, "service": "mindspace-data-collection"})
