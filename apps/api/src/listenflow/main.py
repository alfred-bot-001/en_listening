from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from listenflow.core.config import get_settings
from listenflow.modules.health.routes import router as health_router
from listenflow.modules.materials.routes import router as materials_router
from listenflow.modules.practice.routes import router as practice_router

settings = get_settings()

app = FastAPI(title="ListenFlow API", version="0.1.0")

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


@app.on_event("startup")
def startup() -> None:
    # Ensure default user exists
    from listenflow.db import get_session_factory
    from listenflow.models import User

    session_factory = get_session_factory()
    db = session_factory()
    try:
        from sqlalchemy import select

        user = db.scalar(select(User).where(User.username == "default"))
        if not user:
            user = User(id="default", username="default")
            db.add(user)
            db.commit()
    finally:
        db.close()
