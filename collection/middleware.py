from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

from collection.models import CollectionSession


class ConsentEnforcementMiddleware:
    """
    Middleware that ensures all visitors complete the informed consent form
    before accessing any questionnaires, screening tools, or collection activities.
    """

    EXEMPT_PREFIXES = (
        "/consent",
        "/static",
        "/media",
        "/health",
        "/admin",
        "/favicon.ico",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Whitelist static assets, health checks, admin, and consent URLs
        if any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
            return self.get_response(request)

        # Check if current session has a recorded consent
        session_id = request.session.get("collection_session_id")
        has_consent = False
        if session_id:
            has_consent = CollectionSession.objects.filter(
                session_id=session_id,
                consented_at__isnull=False,
                consent__isnull=False,
            ).exists()

        if not has_consent:
            # If AJAX/JSON API call, return JSON error with redirect directive
            if (
                request.headers.get("x-requested-with") == "XMLHttpRequest"
                or request.content_type == "application/json"
            ):
                return JsonResponse(
                    {"ok": False, "error": "Consent is mandatory before proceeding.", "redirect": "/consent/"},
                    status=403,
                )
            # Otherwise, redirect to the consent page
            return redirect("collection:consent")

        return self.get_response(request)
