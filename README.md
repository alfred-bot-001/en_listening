# English Listening Practice

英语听力练习项目。

## 技术栈

- Frontend: Next.js + React + TypeScript
- Backend: Python + FastAPI
- Database: PostgreSQL
- Queue: Redis + Dramatiq
- Media: ffmpeg + yt-dlp + faster-whisper

## 开发

```bash
docker compose up -d postgres redis
cd apps/api
uv sync --extra dev
uv run uvicorn listenflow.main:app --reload
```

```bash
cd apps/web
npm install
npm run dev
```

