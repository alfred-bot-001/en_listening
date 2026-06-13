from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from listenflow.core.config import get_settings
from listenflow.modules.health.routes import router as health_router
from listenflow.modules.materials.routes import router as materials_router
from listenflow.modules.practice.routes import router as practice_router

settings = get_settings()


def _ensure_default_user() -> None:
    from sqlalchemy import select

    from listenflow.db import get_session_factory
    from listenflow.models import User

    db = get_session_factory()()
    try:
        user = db.scalar(select(User).where(User.username == "default"))
        if not user:
            db.add(User(id="default", username="default"))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    _ensure_default_user()
    yield


app = FastAPI(title="ListenFlow API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(materials_router)
app.include_router(practice_router)

# Serve generated media (per-sentence audio clips) for the practice player.
# The frontend plays `${API_BASE}/storage/{sentence.audio_path}`.
settings.storage_root.mkdir(parents=True, exist_ok=True)
app.mount(
    "/storage",
    StaticFiles(directory=settings.storage_root),
    name="storage",
)
