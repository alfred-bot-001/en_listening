# ListenFlow API

FastAPI backend: material import, the media pipeline (download → transcribe →
segment → clip), and the dictation practice endpoints.

## Requirements

- Python 3.12+
- **ffmpeg / ffprobe** on `PATH` (audio extraction + per-sentence clip cutting)
- PostgreSQL + Redis (see the repo-root `docker-compose.yml`)

## Run

```bash
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn listenflow.main:app --reload   # http://localhost:8000
uv run pytest
```

## Media pipeline

`POST /api/materials/upload` (file) and `POST /api/materials/import` (YouTube /
Bilibili URL) create a `MediaJob` and submit it to the pipeline. Execution is
controlled by `LISTENFLOW_JOB_RUNNER`:

- `eager` — run synchronously inside the request (used by the test suite)
- `thread` — run in a background daemon thread (default; no extra process)
- `dramatiq` — enqueue to the Redis-backed worker, run it with:

```bash
uv run dramatiq listenflow.workers.tasks
```

The pipeline prefers an existing/downloaded subtitle; when none is available it
extracts a 16 kHz mono WAV and transcribes it with faster-whisper. Generated
clips live under `storage/clips/<material_id>/` and are served at
`GET /storage/...` for the practice player.

Poll progress with `GET /api/materials/{material_id}/job`.
