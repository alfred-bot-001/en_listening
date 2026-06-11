from listenflow.modules.materials.schemas import MaterialCreateFromUrl
from listenflow.modules.materials.service import (
    create_url_import_job,
    list_demo_materials,
)


def test_list_demo_materials() -> None:
    materials = list_demo_materials()

    assert len(materials) == 2
    assert materials[0].title == "How AI is changing education"
    assert materials[0].progress_percent == 68


def test_create_url_import_job_detects_youtube() -> None:
    job = create_url_import_job(
        MaterialCreateFromUrl.model_validate(
            {"url": "https://www.youtube.com/watch?v=test"},
        ),
    )

    assert job.status == "queued"
    assert job.current_step == "queued_youtube_download"
    assert job.progress == 0


def test_create_url_import_job_detects_bilibili() -> None:
    job = create_url_import_job(
        MaterialCreateFromUrl.model_validate(
            {"url": "https://www.bilibili.com/video/test"},
        ),
    )

    assert job.current_step == "queued_bilibili_download"
