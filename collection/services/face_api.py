import os

import requests
from django.conf import settings

from .http import configured, post_json


def extract_features(video_file):
    url = configured("FACE_EXTRACT_URL")
    api_key = configured("FACE_EXTRACT_API_KEY")
    if not url or not api_key:
        raise RuntimeError("Face extraction API is not configured.")

    video_file.seek(0)
    filename = os.path.basename(getattr(video_file, "name", "capture.webm"))
    try:
        response = requests.post(
            url,
            headers={"x-api-key": api_key},
            files={"video": (filename, video_file, getattr(video_file, "content_type", "video/webm"))},
            timeout=(30, 1800),
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise RuntimeError("Face extraction request failed.") from exc


def get_session_vector(session_id):
    template = configured("FACE_EXTRACT_SESSION_VECTOR_URL_TEMPLATE")
    api_key = configured("FACE_EXTRACT_API_KEY")
    if not template or not api_key:
        raise RuntimeError("Face session vector API is not configured.")

    url = template.format(session_id=session_id)
    try:
        response = requests.get(url, headers={"x-api-key": api_key}, timeout=(30, 60))
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise RuntimeError("Face session vector request failed.") from exc


def score_features(features):
	return post_json(
		configured("FACE_SCORE_URL"),
        configured("FACE_SCORE_API_KEY"),
		{"vector": features},
		"Face scoring",
	)
