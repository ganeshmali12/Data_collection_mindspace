# MindSpace Data Collection

Standalone Django project for local research data collection. It is intentionally separate from the existing `manovedh` application, database, users, media files, and deployment.

> **Quick Start**: See the comprehensive [Local Setup & Execution Guide](docs/RUN_LOCALLY.md) for step-by-step instructions on running this project locally with Docker or Python.

## Boundary with the original project

This project lives in:

```text
C:\Mindspace_repo\manovedh-data-collection
```

It does not import the original `manovedh` project. It has its own:

- Django settings and URL configuration
- PostgreSQL database for local and production-like work
- media folder for uploaded video and audio
- questionnaire and screening session records
- face, text, voice, and multimodal result records

The original project can be moved to another folder without changing this project. Only update the path used when starting each project.

## Full participant flow

```text
1. Questionnaire
	|
	| Save answers, internal scores, and internal flags
	v
2. Combined activity
	|
	| Browser displays four story images and records camera + microphone video
	v
3. Combined video upload
	|
	| Save video locally
	| Face API: extract features -> score features
	| FFmpeg: extract audio from video
	| Sarvam/API: speech to text
	| Text API: extract parameters -> score parameters
	v
4. Voice phonation
	|
	| Record and save seven individual sounds
	v
5. Voice processing
	|
	| FFmpeg combines the seven recordings
	| Voice API: extract features -> PCA -> score features
	v
6. Multimodal fusion
	|
	| Combine face, text, and voice features
	| Fusion API scores the combined feature set
	v
7. Completion
```

The participant sees neutral questionnaire language. Internal questionnaire scores and flags are stored but are not shown to the participant.

## Local database

The active local database is PostgreSQL, running in Docker:

```text
mindspace_collection
```

The database engine is selected in `.env`:

```env
DB_ENGINE=postgresql
DB_NAME=mindspace_collection
DB_USER=mindspace_user
DB_PASSWORD=mindspace_local_password
DB_HOST=127.0.0.1
DB_PORT=5432
```

The old `data_collection.sqlite3` file is kept as a backup and is no longer the active database.

When running in Docker Compose, the Django container connects to PostgreSQL using
the internal service name `postgres`. The host port remains available at
`127.0.0.1:5432` for local tools.

### Stored database records

#### `CollectionSession`

One record for one participant run. It stores:

- session UUID
- optional participant code
- workflow status
- current workflow step
- creation and update timestamps

#### `QuestionnaireResponse`

One response linked to a collection session. It stores:

- all questionnaire answers
- internal questionnaire scores
- internal flags
- submission time

These fields are private application data and are not displayed in the participant UI.

#### `MediaCapture`

One record for every uploaded file. It stores:

- linked collection session
- `combined_video` or `phonation_audio`
- stored file path
- duration, sound ID, hold time, and other metadata
- upload status
- creation time

#### `AnalysisResult`

One result per session and modality. The current modalities are:

- `face`
- `text`
- `voice`
- `multimodal`

It stores:

- processing status
- transcript where applicable
- complete raw API response
- normalized result
- error message if processing failed
- processing timestamps

## Local media storage

Uploaded video and audio files are stored separately from the database under session-specific folders:
```text
	C:\Mindspace_repo\manovedh-data-collection\media\captures\session_<session-uuid>\
```

For example:

```text
media\captures\session_<session-uuid>\combined_video\combined_video_<id>.webm
media\captures\session_<session-uuid>\voice_phonation\sound_03_<id>.webm
```

The database stores the Django file reference. The actual binary video/audio remains in the `media` folder. Existing files created before this organization change keep their old names; new uploads use the session-specific structure.

## API processing configuration

API settings are loaded from:

```text
C:\Mindspace_repo\manovedh-data-collection\.env
```

The configured services are:

```env
FACE_EXTRACT_URL=...
FACE_SCORE_URL=...
FACE_VIDEO_FEATURE_EXTRACTION_API_KEY=...
FACE_VIDEO_FEATURE_TO_MH_API_KEY=...

TEXT_EXTRACT_URL=...
TEXT_SCORE_URL=...
TEXT_PARAMETER_EXTRACT_API_KEY=...
TEXT_ANALYSIS_API_KEY=...
SARVAM_API_KEY=...

VOICE_EXTRACT_URL=...
VOICE_PCA_URL=...
VOICE_SCORE_URL=...
VOICE_FEATURE_EXTRACT_API_KEY=...
VOICE_PCA_API_KEY=...
VOICE_FEATURE_TO_MH=...

FUSION_SCORE_URL=...
FUSION_API_KEY=...
```

The API calls run on the server side. Browser code uploads media to Django; Django calls the external services and stores their responses in `AnalysisResult`.

Never commit real API keys. Any key previously exposed outside the local `.env` file should be rotated.

## Main URLs

Participant pages:

```text
http://127.0.0.1:8000/questionnaire/
http://127.0.0.1:8000/screening/combined/
http://127.0.0.1:8000/screening/voice/
http://127.0.0.1:8000/screening/completed/
```

Operational endpoint:

```text
http://127.0.0.1:8000/health/
http://127.0.0.1:8000/screening/status/
```

Admin:

```text
http://127.0.0.1:8000/admin/
```

## Run locally every time

Open PowerShell and run:

```powershell
cd C:\Mindspace_repo\manovedh-data-collection
docker compose up -d
```

Then open:

```text
http://127.0.0.1:8000/questionnaire/
```

The Compose web container runs migrations and serves the application on port 8000.
Stop the containers with `docker compose down`.

To expose the data-collection application directly on the VPS Tailscale interface,
set this value in `.env` before starting the stack:

```env
DATA_COLLECTION_BIND_IP=100.x.y.z
```

Use the VPS's actual Tailscale address. Leaving it as `127.0.0.1` keeps the
application private to the host and lets host nginx proxy it.

## First-time setup

```powershell
cd C:\Mindspace_repo\manovedh-data-collection
docker compose up -d
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py test
```

FFmpeg must also be installed and available on PATH because it is used to extract audio from video and combine the seven phonation recordings.

## Inspect stored data

### Django admin

Create an administrator once:

```powershell
python manage.py createsuperuser
```

Start the server and open `/admin/`. The current admin registration exposes collection sessions and questionnaire responses. PostgreSQL and the media folder are the authoritative local storage locations.

### PostgreSQL viewer

Connect using pgAdmin, DBeaver, or another PostgreSQL client:

```text
Host: 127.0.0.1
Port: 5432
Database: mindspace_collection
User: mindspace_user
Password: mindspace_local_password
```

Useful tables are:

```text
collection_collectionsession
collection_questionnaireresponse
collection_mediacapture
collection_analysisresult
```

The exact table names can be confirmed with:

```powershell
python manage.py showmigrations
```

## Check that the local flow is working

Run the automated checks:

```powershell
python manage.py check
python manage.py test
```

Check the server health endpoint:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health/
```

Then manually test:

1. Submit the questionnaire.
2. Confirm the browser opens the combined activity.
3. Record and upload the combined video.
4. Confirm a video appears under `media\captures\session_<session-uuid>\combined_video\`.
5. Complete all seven phonation sounds.
6. Confirm seven audio files appear under `media\captures\session_<session-uuid>\voice_phonation\`.
7. Inspect `AnalysisResult` records after API processing.

If external APIs are unavailable, the pages can still be tested, but analysis records will move to `failed` and contain an error message.

## Move the original project

The standalone project does not require the original folder to remain beside it. Before moving the original project:

1. Stop any server running from `manovedh`.
2. Keep `manovedh-data-collection` in its current folder or move it independently.
3. Move the original `manovedh` folder to the desired location.
4. Start this project using its new absolute path if this project is also moved.
5. Do not copy the original database or media folder into this project.

Example after moving this project to `D:\Mindspace\data-collection`:

```powershell
cd D:\Mindspace\data-collection
.\.venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

If `.venv` does not work after a folder move, recreate it:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Reset only local test data

This permanently deletes local participant records and uploaded captures:

```powershell
docker compose down -v
docker compose up -d
\.\.venv\Scripts\Activate.ps1
python manage.py migrate
Remove-Item .\media\captures\* -Recurse -Force
```

Do not run this command if the local recordings or results need to be kept.

## Important safety notes

- This is a research data-collection pipeline, not a diagnostic tool.
- Keep participant identifiers separate from direct personal identity wherever possible.
- Protect the `.env` file and rotate exposed API credentials.
- Do not use Django's development server for VPS production deployment.
- Back up both the database and `media` directory before deleting or moving data.
