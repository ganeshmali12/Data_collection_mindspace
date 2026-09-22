import os

import requests

from .http import TIMEOUT, configured, post_json


def extract_features(audio_file):
	url = configured("VOICE_EXTRACT_URL")
	api_key = configured("VOICE_EXTRACT_API_KEY")
	if not url or not api_key:
		raise RuntimeError("Voice extraction API is not configured.")

	audio_file.seek(0)
	filename = os.path.basename(getattr(audio_file, "name", "phonation.wav"))
	try:
		response = requests.post(
			url,
			headers={"x-api-key": api_key},
			files={"file": (filename, audio_file, "audio/wav")},
			timeout=(60, 1800),
		)
		response.raise_for_status()
		return response.json()
	except requests.RequestException as exc:
		raise RuntimeError("Voice extraction request failed.") from exc


def process_pca(features):
	return post_json(
		configured("VOICE_PCA_URL"),
		configured("VOICE_PCA_API_KEY"),
		{"features": features},
		"Voice PCA",
	)


def score_features(components):
	return post_json(
		configured("VOICE_SCORE_URL"),
		configured("VOICE_SCORE_API_KEY"),
		components,
		"Voice scoring",
	)
