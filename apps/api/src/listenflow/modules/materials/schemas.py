from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class MaterialStatus(StrEnum):
    CREATED = "created"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    DOWNLOADING = "downloading"
    EXTRACTING_SUBTITLE = "extracting_subtitle"
    TRANSCRIBING = "transcribing"
    SEGMENTING = "segmenting"
    READY = "ready"
    FAILED = "failed"


class SourceType(StrEnum):
    UPLOAD = "upload"
    YOUTUBE = "youtube"
    BILIBILI = "bilibili"


class MaterialCreateFromUrl(BaseModel):
    url: HttpUrl
    title: str | None = None
    group_size: int = Field(default=10, ge=1, le=50)


class MaterialSummary(BaseModel):
    id: UUID
    title: str
    source_type: SourceType
    status: MaterialStatus
    group_size: int
    sentence_count: int = 0
    progress_percent: int = 0


class MaterialJob(BaseModel):
    id: UUID
    material_id: UUID
    status: str
    current_step: str
    progress: int = Field(ge=0, le=100)
    error_message: str | None = None
