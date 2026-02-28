# Norm AI Full-Stack Take-Home

This repository contains:
- A FastAPI backend that loads and indexes `docs/laws.pdf` for natural-language Q&A with citations.
- A Next.js frontend that calls the backend and visualizes response + citations.

## Prerequisites

- Python 3.9+
- Node.js 18+
- `OPENAI_API_KEY` environment variable

## Environment Variables

This project supports both:
- local `.env` loading for developer convenience
- explicit runtime environment injection for Docker / CI

Recommended local setup:

1. Copy the template:

```bash
cp .env.example .env
```

2. Fill in your real key in `.env`.

## Backend (Local)

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will automatically load `OPENAI_API_KEY` from `.env` if present.

3. Open Swagger docs:

`http://localhost:8000/docs`

Use `GET /query` with a query string such as:
- `What happens if I steal from a sept?`
- `Is slavery legal in the Seven Kingdoms?`

## Backend (Docker)

1. Build image:

```bash
docker build -t norm-takehome-backend .
```

2. Run container:

```bash
docker run --rm -p 8000:8000 -e OPENAI_API_KEY=$OPENAI_API_KEY norm-takehome-backend
```

You can also pass a local env file:

```bash
docker run --rm -p 8000:8000 --env-file .env norm-takehome-backend
```

3. Open Swagger docs:

`http://localhost:8000/docs`

## Frontend

1. Install dependencies:

```bash
cd frontend
npm install
```

2. (Optional) set backend base URL:

```bash
cp .env.local.example .env.local
```

3. Start frontend:

```bash
npm run dev
```

4. Open:

`http://localhost:3000`

## Design Choices / Assumptions

- The backend parses numbered sections from the laws PDF and stores semantically meaningful chunks.
- Retrieval uses a local in-memory LlamaIndex vector index for this exercise.
- Citations are sourced from retrieved nodes and returned with section-aware metadata.
- The frontend focuses on a lightweight evaluator-friendly workflow: ask question, read answer, inspect citations.

For more detailed implementation notes and tradeoff reasoning, see `TRADEOFFS.md`.
