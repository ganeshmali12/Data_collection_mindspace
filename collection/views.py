import json
import random
from pathlib import Path

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import CollectionSession, MediaCapture, QuestionnaireResponse
from .services.combined_processing import process_combined_capture
from .services.voice_processing import process_voice_session
from .services.fusion_processing import process_fusion_session


STORY_IMAGE_DIR = Path(__file__).resolve().parent.parent / "static" / "images" / "activities" / "story"


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


def home(request):
    return redirect("collection:questionnaire")


@ensure_csrf_cookie
def questionnaire(request):
    return render(request, "collection/questionnaire.html")


def get_collection_session(request):
    session_id = request.session.get("collection_session_id")
    session = CollectionSession.objects.filter(session_id=session_id).first() if session_id else None
    if not session:
        session = CollectionSession.objects.create()
        request.session["collection_session_id"] = str(session.session_id)
    return session


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
        process_combined_capture(capture.pk, transcript=transcript)
    except MediaCapture.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Capture not found."}, status=404)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)
    return JsonResponse({"ok": True, "message": "Face and text processing finished."})


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
         "required_hold_ms": 900, "voice_threshold": 30, "accepted": []}
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
        process_fusion_session(session)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)
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
