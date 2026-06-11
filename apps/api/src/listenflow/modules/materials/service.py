from dataclasses import dataclass
from uuid import UUID, uuid4

from listenflow.modules.materials.schemas import (
    MaterialCreateFromUrl,
    MaterialJob,
    MaterialStatus,
    MaterialSummary,
    SourceType,
)


@dataclass(frozen=True)
class DemoMaterial:
    id: UUID
    title: str
    source_type: SourceType
    status: MaterialStatus
    group_size: int
    sentence_count: int
    progress_percent: int


DEMO_MATERIALS: tuple[DemoMaterial, ...] = (
    DemoMaterial(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        title="How AI is changing education",
        source_type=SourceType.YOUTUBE,
        status=MaterialStatus.READY,
        group_size=10,
        sentence_count=42,
        progress_percent=68,
    ),
    DemoMaterial(
        id=UUID("22222222-2222-4222-8222-222222222222"),
        title="Product thinking podcast",
        source_type=SourceType.UPLOAD,
        status=MaterialStatus.TRANSCRIBING,
        group_size=10,
        sentence_count=0,
        progress_percent=46,
    ),
)


def list_demo_materials() -> list[MaterialSummary]:
    return [
        MaterialSummary(
            id=material.id,
            title=material.title,
            source_type=material.source_type,
            status=material.status,
            group_size=material.group_size,
            sentence_count=material.sentence_count,
            progress_percent=material.progress_percent,
        )
        for material in DEMO_MATERIALS
    ]


def create_url_import_job(payload: MaterialCreateFromUrl) -> MaterialJob:
    material_id = uuid4()
    current_step = "queued_url_import"
    if "youtube.com" in str(payload.url) or "youtu.be" in str(payload.url):
        current_step = "queued_youtube_download"
    if "bilibili.com" in str(payload.url):
        current_step = "queued_bilibili_download"
    return MaterialJob(
        id=uuid4(),
        material_id=material_id,
        status="queued",
        current_step=current_step,
        progress=0,
    )
