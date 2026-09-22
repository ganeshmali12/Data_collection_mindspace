import requests
from django.conf import settings


TIMEOUT = (30, 900)


def post_json(url, api_key, payload, label):
    if not url:
        raise RuntimeError(f"{label} URL is not configured.")
    if not api_key:
        raise RuntimeError(f"{label} API key is not configured.")

    try:
        response = requests.post(
            url,
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"{label} request failed.") from exc


def configured(name):
    return str(getattr(settings, name, "") or "").strip()