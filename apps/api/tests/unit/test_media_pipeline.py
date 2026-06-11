from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from listenflow.db import Base
from listenflow.models import JobStatus, Material, MaterialType, MediaJob, Sentence
from listenflow.workers.media_pipeline import (
    PIPELINE_STEPS,
    parse_transcript,
    plan_media_pipeline,
    process_media_job,
)


def test_plan_media_pipeline_uses_all_steps() -> None:
    material_id = UUID("11111111-1111-4111-8111-111111111111")

    plan = plan_media_pipeline(material_id)

    assert len(plan) == len(PIPELINE_STEPS)
    assert plan[0][0] == material_id
    assert plan[-1][1].progress == 100


def test_parse_srt_transcript() -> None:
    segments = parse_transcript(
        """
1
00:00:01,000 --> 00:00:03,500
Students learn better.

2
00:00:04.000 --> 00:00:06.000
Practice is immediate.
"""
    )

    assert [segment.text for segment in segments] == [
        "Students learn better.",
        "Practice is immediate.",
    ]
    assert segments[0].start_time == 1
    assert segments[1].end_time == 6


def test_parse_plain_text_transcript() -> None:
    segments = parse_transcript("Students learn better. Practice is immediate.")

    assert len(segments) == 2
    assert segments[0].start_time == 0
    assert segments[1].start_time == 3


def test_process_media_job_creates_sentences(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        transcript_path = tmp_path / "uploads" / "sample.srt"
        transcript_path.parent.mkdir()
        transcript_path.write_text(
            """
1
00:00:01,000 --> 00:00:03,000
Students learn better when practice is immediate.
""",
            encoding="utf-8",
        )

        with Session(engine) as db:
            material = Material(
                id="material1",
                title="Sample",
                source_type=MaterialType.AUDIO,
                file_path="uploads/sample.srt",
            )
            job = MediaJob(id="job1", material_id="material1", status=JobStatus.PENDING)
            db.add_all([material, job])
            db.commit()

            processed = process_media_job(db, "job1", storage_root=tmp_path)
            sentence = db.scalar(
                select(Sentence).where(Sentence.material_id == "material1")
            )

            assert processed.status == JobStatus.DONE
            assert processed.progress == 100
            assert sentence is not None
            assert sentence.group_index == 0
            assert sentence.keywords == '["Students", "learn", "better"]'
    finally:
        engine.dispose()
