import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from listenflow.core.config import get_settings
from listenflow.db import Base, get_db
from listenflow.models import Favorite, Material, MaterialType, MediaJob, Sentence
from listenflow.modules.health.routes import router as health_router
from listenflow.modules.materials.routes import router as materials_router
from listenflow.modules.practice.routes import router as practice_router
from listenflow.workers import download

FFMPEG = shutil.which("ffmpeg")


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("LISTENFLOW_STORAGE_ROOT", str(tmp_path))
    # Run the media pipeline synchronously inside the request so tests can
    # assert the final job state without polling a background thread.
    monkeypatch.setenv("LISTENFLOW_JOB_RUNNER", "eager")
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    app = FastAPI()
    app.include_router(health_router)
    app.include_router(materials_router)
    app.include_router(practice_router)
    app.mount("/storage", StaticFiles(directory=str(tmp_path)), name="storage")

    def override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(engine)
    engine.dispose()
    get_settings.cache_clear()


def test_upload_text_transcript_processes_material(client: TestClient) -> None:
    response = client.post(
        "/api/materials/upload",
        data={"title": "Transcript"},
        files={
            "file": ("sample.txt", b"Students learn better. Practice is immediate.")
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Transcript"
    assert body["job_status"] == "done"

    group = client.get(f"/api/practice/continue/{body['id']}")

    assert group.status_code == 200
    sentences = group.json()["group"]["sentences"]
    assert sentences[0]["keywords"] == ["Students", "learn", "better"]


def test_import_url_without_downloader_fails_gracefully(client: TestClient) -> None:
    """yt-dlp is not installed in the test env, so the job should fail clearly."""
    created = client.post(
        "/api/materials/import",
        json={"url": "https://www.youtube.com/watch?v=test", "title": "YT"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["source_type"] == "youtube"

    job = client.get(f"/api/materials/{body['id']}/job")
    assert job.status_code == 200
    assert job.json()["status"] == "failed"
    assert "yt-dlp" in job.json()["error_message"]


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg required to cut audio clips")
def test_import_url_with_fake_downloader_runs_full_pipeline(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    """Patch the downloader to a local subtitle + audio, exercising the whole
    remote pipeline: parse subtitles -> segment -> cut per-sentence clips."""
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    srt = fixtures / "captions.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nStudents learn better.\n\n"
        "2\n00:00:02,000 --> 00:00:04,000\nPractice is immediate.\n",
        encoding="utf-8",
    )
    media = fixtures / "audio.wav"
    subprocess.run(
        [
            FFMPEG, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
            "-ar", "16000", "-ac", "1", str(media),
        ],
        check=True,
        capture_output=True,
    )

    def fake_download(url, dest_dir, *, stem, subtitle_langs=()):
        return download.DownloadResult(media_path=media, subtitle_path=srt)

    monkeypatch.setattr(download, "download_media", fake_download)

    created = client.post(
        "/api/materials/import",
        json={"url": "https://www.youtube.com/watch?v=test", "title": "YT"},
    )
    body = created.json()
    assert body["job_status"] == "done"

    group = client.get(f"/api/practice/continue/{body['id']}").json()["group"]
    sentences = group["sentences"]
    assert [s["text"] for s in sentences] == [
        "Students learn better.",
        "Practice is immediate.",
    ]
    # Per-sentence audio clips were cut and are reachable under /storage.
    assert sentences[0]["audio_path"].startswith("clips/")
    clip = client.get(f"/storage/{sentences[0]['audio_path']}")
    assert clip.status_code == 200
    assert len(clip.content) > 0


def test_import_url_rejects_unsupported_source(client: TestClient) -> None:
    response = client.post(
        "/api/materials/import",
        json={"url": "https://example.com/video"},
    )

    assert response.status_code == 400


def test_process_material_reports_missing_source(client: TestClient) -> None:
    """A material with no transcript and no audio cannot be processed."""
    db_iter = client.app.dependency_overrides[get_db]()
    db = next(db_iter)
    try:
        db.add(
            Material(id="empty", title="Empty", source_type=MaterialType.AUDIO)
        )
        db.add(MediaJob(id="emptyjob", material_id="empty"))
        db.commit()
    finally:
        db.close()

    processed = client.post("/api/materials/empty/process")

    assert processed.status_code == 200
    assert processed.json()["status"] == "failed"
    assert "No source file" in processed.json()["error_message"]


def test_delete_material(client: TestClient) -> None:
    created = client.post(
        "/api/materials/import",
        json={"url": "https://youtu.be/test", "title": "Delete Me"},
    )

    deleted = client.delete(f"/api/materials/{created.json()['id']}")
    listed = client.get("/api/materials")

    assert deleted.status_code == 204
    assert listed.json() == []


def test_practice_submit_favorites_and_wrongbook(client: TestClient) -> None:
    material_id = _seed_sentence(client)

    group = client.get(f"/api/practice/group/{material_id}/0")
    sentence_id = group.json()["sentences"][0]["id"]

    favorite = client.post(f"/api/practice/favorite/{sentence_id}")
    favorites = client.get("/api/practice/favorites")
    wrong = client.post(
        "/api/practice/submit",
        json={"sentence_id": sentence_id, "answers": {"Students": "teacher"}},
    )
    wrongbook = client.get("/api/practice/wrongbook")
    correct = client.post(
        "/api/practice/submit",
        json={"sentence_id": sentence_id, "answers": {"Students": "students"}},
    )
    removed = client.delete(f"/api/practice/favorite/{sentence_id}")

    assert favorite.status_code == 201
    assert favorites.json()[0]["is_favorite"] is True
    assert wrong.json()["all_correct"] is False
    assert wrongbook.json()[0]["wrong_count"] == 1
    assert correct.json()["all_correct"] is True
    assert removed.json() == {"status": "removed"}


def _seed_sentence(client: TestClient) -> str:
    db_iter = client.app.dependency_overrides[get_db]()
    db = next(db_iter)
    try:
        material = Material(
            id="seedmaterial",
            title="Seed",
            source_type=MaterialType.AUDIO,
        )
        db.add(material)
        db.add(MediaJob(id="seedjob", material_id=material.id))
        db.add(
            Sentence(
                id="seedsentence",
                material_id=material.id,
                group_index=0,
                sentence_index=0,
                text="Students learn better.",
                start_time=0,
                end_time=2,
                keywords=json.dumps(["Students"]),
            )
        )
        db.commit()

        assert db.scalar(select(Favorite)) is None
        return material.id
    finally:
        db.close()
