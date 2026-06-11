from uuid import UUID

from pydantic import BaseModel


class BlankView(BaseModel):
    id: UUID
    order_index: int
    placeholder: str = "____"


class PracticeSentence(BaseModel):
    id: UUID
    material_title: str
    group_title: str
    order_index: int
    text_before: str
    text_after: str
    audio_url: str
    blanks: list[BlankView]


class AnswerSubmission(BaseModel):
    answers: dict[UUID, str]


class BlankResult(BaseModel):
    blank_id: UUID
    correct: bool


class AnswerResponse(BaseModel):
    all_correct: bool
    results: list[BlankResult]
    added_to_wrongbook: bool
