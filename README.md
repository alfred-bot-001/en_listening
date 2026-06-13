# English Listening Practice

英语听力练习项目。

## 技术栈

- Frontend: Next.js + React + TypeScript
- Backend: Python + FastAPI
- Database: PostgreSQL
- Queue: Redis + Dramatiq
- Media: ffmpeg + yt-dlp + faster-whisper

> 前置依赖：本机需安装 **ffmpeg**（音频提取与句子切片）。导入 YouTube/Bilibili
> 需要 `yt-dlp`，无字幕时的自动转写需要 `faster-whisper`，二者均随 `uv sync` 安装。

## 开发

后端（API）：

```bash
docker compose up -d postgres redis
cd apps/api
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn listenflow.main:app --reload   # http://localhost:8000
```

媒体任务默认在后台线程执行（`LISTENFLOW_JOB_RUNNER=thread`）。生产可改用
Dramatiq worker：

```bash
LISTENFLOW_JOB_RUNNER=dramatiq uv run dramatiq listenflow.workers.tasks
```

前端（Web）：

```bash
cd apps/web
npm install
npm run dev
```

环境变量见 `.env.example`（后端 `LISTENFLOW_*`，前端 `NEXT_PUBLIC_API_URL`）。

