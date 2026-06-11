import json
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
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


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("LISTENFLOW_STORAGE_ROOT", str(tmp_path))
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


def test_import_url_and_job_status(client: TestClient) -> None:
    created = client.post(
        "/api/materials/import",
        json={"url": "https://www.youtube.com/watch?v=test", "title": "YT"},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["source_type"] == "youtube"
    assert body["job_status"] == "pending"

    job = client.get(f"/api/materials/{body['id']}/job")

    assert job.status_code == 200
    assert job.json()["status"] == "pending"


def test_import_url_rejects_unsupported_source(client: TestClient) -> None:
    response = client.post(
        "/api/materials/import",
        json={"url": "https://example.com/video"},
    )

    assert response.status_code == 400


def test_process_material_reports_missing_transcript(client: TestClient) -> None:
    created = client.post(
        "/api/materials/import",
        json={"url": "https://www.bilibili.com/video/test", "title": "Bili"},
    )
    material_id = created.json()["id"]

    processed = client.post(f"/api/materials/{material_id}/process")

    assert processed.status_code == 200
    assert processed.json()["status"] == "failed"
    assert "No transcript file" in processed.json()["error_message"]


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
