# MindSpace Data Collection — Local Setup & Execution Guide

This document provides step-by-step instructions for setting up and running the **MindSpace Data Collection** project on your local machine (Windows, macOS, or Linux).

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Prerequisites & System Requirements](#prerequisites--system-requirements)
3. [Environment Configuration (`.env`)](#environment-configuration-env)
4. [Method 1: Running with Docker (Recommended)](#method-1-running-with-docker-recommended)
5. [Method 2: Running Natively (Python Virtual Environment)](#method-2-running-natively-python-virtual-environment)
6. [Accessing the Application](#accessing-the-application)
7. [Creating an Admin Account & Inspecting Data](#creating-an-admin-account--inspecting-data)
8. [Running Tests & Verifying System Health](#running-tests--verifying-system-health)
9. [Troubleshooting & Common Issues](#troubleshooting--common-issues)

---

## Project Overview

MindSpace Data Collection is a standalone Django application built for multimodal participant data collection:

```text
[ Participant Questionnaire ]
             │
             ▼
[ Combined Activity (Camera + Mic Video) ]
             │
             ▼
[ Combined Processing (Face API + FFmpeg Audio Extract + Sarvam STT + Text API) ]
             │
             ▼
[ Voice Phonation (7 Guided Audio Recordings) ]
             │
             ▼
[ Voice Processing (FFmpeg Concatenation + Voice API + PCA + Scoring) ]
             │
             ▼
[ Multimodal Fusion (Combined Feature Analysis) ]
             │
             ▼
[ Completion & Storage ]
```

---

## Prerequisites & System Requirements

### For Docker Setup (Method 1 - Quickest & Recommended)
- **Docker Desktop** installed and running ([Download Docker](https://www.docker.com/products/docker-desktop/))
- **Git**

### For Native Setup (Method 2)
- **Python 3.11+ or 3.12** ([python.org](https://www.python.org/))
- **FFmpeg** installed and accessible in your system's `PATH` (required for video/audio processing).
  - *Windows (via winget)*: `winget install Gyan.FFmpeg` or `winget install "FFmpeg (Essentials Build)"`
  - *macOS (via Homebrew)*: `brew install ffmpeg`
  - *Linux (Ubuntu/Debian)*: `sudo apt-get update && sudo apt-get install ffmpeg`
- **PostgreSQL 16** (or use Docker for PostgreSQL, or SQLite for quick local trials)
- **Git**

---

## Environment Configuration (`.env`)

Before starting, ensure you have a `.env` file in the root directory of the project.

You can copy the template if `.env` does not exist:

```bash
# Windows PowerShell
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

### Key `.env` Parameters

```ini
# Django settings
SECRET_KEY=local-secret-key-change-me-for-production
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost,testserver
CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000

# Database selection (postgresql or sqlite)
DB_ENGINE=postgresql
DB_NAME=mindspace_collection
DB_USER=mindspace_user
DB_PASSWORD=mindspace_local_password
DB_HOST=127.0.0.1
DB_PORT=5432

# Application Bind Settings
DATA_COLLECTION_BIND_IP=127.0.0.1
DATA_COLLECTION_PORT=8000

# External ML & Speech APIs
FACE_EXTRACT_URL=http://<host>:5100/extract/video
FACE_EXTRACT_SESSION_VECTOR_URL_TEMPLATE=http://<host>:5100/extract/session/{session_id}/vector
FACE_SCORE_URL=http://<host>:5200/score
FACE_VIDEO_FEATURE_EXTRACTION_API_KEY=your_key_here
FACE_VIDEO_FEATURE_TO_MH_API_KEY=your_key_here

TEXT_EXTRACT_URL=http://<host>:8025/analyze
TEXT_SCORE_URL=http://<host>:5500/predict
TEXT_PARAMETER_EXTRACT_API_KEY=your_key_here
TEXT_ANALYSIS_API_KEY=your_key_here

SARVAM_API_KEY=your_sarvam_api_key_here
SARVAM_STT_MODEL=saaras:v3

VOICE_EXTRACT_URL=http://<host>:5800/extract
VOICE_PCA_URL=http://<host>:5900/process
VOICE_SCORE_URL=http://<host>:5600/predict
VOICE_FEATURE_EXTRACT_API_KEY=your_key_here
VOICE_PCA_API_KEY=your_key_here
VOICE_FEATURE_TO_MH=your_key_here

FUSION_SCORE_URL=http://<host>:8010/predict
FUSION_API_KEY=your_key_here
```

> [!NOTE]
> When testing locally without active ML microservices, the web workflow and media capture will still work seamlessly; the background analysis tasks will record their status in the database.

---

## Method 1: Running with Docker (Recommended)

Docker Compose sets up both the **PostgreSQL 16 database** and the **Django application container (with FFmpeg and Daphne)** automatically.

### 1. Start the Containers

Open your terminal / PowerShell in the project root:

```bash
docker compose up -d --build
```

This will:
- Build the web image with Python 3.12 and FFmpeg pre-installed.
- Start the PostgreSQL 16 database container.
- Apply database migrations and collect static files automatically upon startup.
- Launch the Daphne ASGI web server on `http://127.0.0.1:8000`.

### 2. Check Container Status & Logs

```bash
# Check running containers
docker compose ps

# View live application logs
docker compose logs -f web

# View database logs
docker compose logs -f postgres
```

### 3. Create a Django Superuser (Admin)

```bash
docker compose exec web python manage.py createsuperuser
```
Follow the prompts to enter a username, email, and password.

### 4. Stop the Containers

```bash
# Stop containers while preserving data
docker compose down

# Stop containers and wipe database volumes (clean reset)
docker compose down -v
```

---

## Method 2: Running Natively (Python Virtual Environment)

If you prefer running Python directly on your host machine:

### 1. Create and Activate a Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Python Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Ensure FFmpeg is Installed & on PATH

Verify by running:
```bash
ffmpeg -version
```
If this command is not found, install FFmpeg according to the [Prerequisites](#for-native-setup-method-2) section.

### 4. Set Up the Database

You have two choices for the database when running natively:

#### Choice A: Use Docker for PostgreSQL only (Recommended)
Start just the PostgreSQL container:
```bash
docker compose up -d postgres
```

#### Choice B: Use SQLite for lightweight offline testing
Edit your `.env` file:
```ini
DB_ENGINE=sqlite
DB_NAME=data_collection.sqlite3
```

### 5. Run Database Migrations

```bash
python manage.py migrate
```

### 6. Create Superuser (Admin)

```bash
python manage.py createsuperuser
```

### 7. Run the Development Server

You can run with Django's standard server:
```bash
python manage.py runserver 127.0.0.1:8000
```
Or with Daphne (matching the production ASGI server):
```bash
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

---

## Accessing the Application

Once the server is running, open your web browser to:

| Page / Endpoint | URL | Description |
| :--- | :--- | :--- |
| **Participant Questionnaire (Start)** | `http://127.0.0.1:8000/questionnaire/` | Starting point for participants |
| **Combined Activity** | `http://127.0.0.1:8000/screening/combined/` | Story image narration & video recording |
| **Voice Phonation** | `http://127.0.0.1:8000/screening/voice/` | Guided 7-sound phonation recording |
| **Completion Page** | `http://127.0.0.1:8000/screening/completed/` | End of screening flow |
| **Django Admin** | `http://127.0.0.1:8000/admin/` | Admin panel for inspection |
| **Health Check** | `http://127.0.0.1:8000/health/` | API / service status check |
| **Workflow Status** | `http://127.0.0.1:8000/screening/status/` | Current session workflow JSON |

> [!TIP]
> **Browser Camera & Mic Permissions**: Browsers enforce strict security for WebRTC/MediaDevices. Accessing via `http://localhost:8000` or `http://127.0.0.1:8000` is treated as a secure context, allowing webcam and microphone prompts to appear normally.

---

## Creating an Admin Account & Inspecting Data

### Django Admin Portal
Navigate to `http://127.0.0.1:8000/admin/` and log in with your superuser credentials.

You can inspect:
- **Collection Sessions**: Participant session identifiers, workflow states, and timestamps.
- **Questionnaire Responses**: Recorded questionnaire submissions.
- **Media Captures**: Paths and metadata for recorded video and audio files.
- **Analysis Results**: Results, transcripts, and status of Face, Text, Voice, and Multimodal Fusion pipelines.

### Connecting to PostgreSQL via Database Client
You can inspect the database using tools like DBeaver, pgAdmin, or VS Code Database Client:

- **Host**: `127.0.0.1`
- **Port**: `5432`
- **Database**: `mindspace_collection`
- **Username**: `mindspace_user`
- **Password**: `mindspace_local_password`

### Stored Media Files
Uploaded recordings are stored in session-isolated directories under:
```text
media/captures/session_<session-uuid>/combined_video/
media/captures/session_<session-uuid>/voice_phonation/
```

---

## Running Tests & Verifying System Health

### Run Automated Tests

**Using Docker:**
```bash
docker compose exec web python manage.py test
```

**Natively:**
```bash
python manage.py test
```

### Health Check Endpoint

You can query the health endpoint:

**PowerShell:**
```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health/
```

**cURL:**
```bash
curl -i http://127.0.0.1:8000/health/
```

Expected JSON response:
```json
{"status": "ok", "database": "ok"}
```

---

## Troubleshooting & Common Issues

### 1. `ffmpeg: command not found` (Native Run)
- **Problem**: Voice phonation merging or video audio extraction fails.
- **Fix**: Install FFmpeg and add the binary folder to your system `PATH`. Restart your terminal. If using Docker, FFmpeg is already installed inside the container.

### 2. `Database connection failed` or `Connection refused`
- **Problem**: Django cannot connect to PostgreSQL.
- **Fix**:
  - If using Docker Compose, make sure `postgres` container is healthy (`docker compose ps`).
  - In Docker, Django connects to host `postgres`. Natively, it connects to `127.0.0.1`. Verify `DB_HOST` in `.env`.
  - Check if port `5432` is already occupied by a local PostgreSQL installation. Change `POSTGRES_HOST_PORT` in `.env` if needed.

### 3. Browser does not allow camera/microphone
- **Problem**: Media stream fails to open or permissions are blocked.
- **Fix**:
  - Always use `http://127.0.0.1:8000` or `http://localhost:8000` (not a raw LAN IP unless configured with HTTPS).
  - Check browser site settings to ensure microphone and camera permissions are granted.

### 4. Resetting Local Test Data
To completely reset all local database entries and uploaded media:

```powershell
# Reset Docker database volume
docker compose down -v
docker compose up -d

# Clear local media captures
Remove-Item .\media\captures\* -Recurse -Force
```
*(On Linux/macOS, use `rm -rf media/captures/*`)*
