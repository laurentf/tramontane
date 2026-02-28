# Tramontane

Autonomous self-hosted web radio powered by AI.

**Mistral Worldwide Hackathon — February 2026 (Online Edition)**

## What is it

Tramontane is a platform for running AI-driven web radio stations. Define radio hosts with their own personality, background, and style. Set the radio theme, topics of interest, manage planning and scheduling, and let the AI handle interviews, podcasts, and live content autonomously.

## Stack

- **Backend:** FastAPI + asyncpg + Supabase (auth, DB, storage)
- **Frontend:** Vue 3 + Vite + Tailwind CSS
- **AI:** Mistral (LLM, embeddings, analysis)
- **Workers:** ARQ (Redis-based async job queue)
- **Infra:** Docker Compose (API + web + worker + Redis)

## Prerequisites

### 1. Supabase project

Create a free project at [supabase.com](https://supabase.com):

1. Create a new project
2. Fill in the Supabase env keys in `.env`
3. Use the **transaction pooler** connection string for `DATABASE_URL`

### 2. Google OAuth

Set up Google SSO for authentication:

1. Go to [Google Cloud Console > Credentials](https://console.cloud.google.com/apis/credentials)
2. Create (or select) an OAuth 2.0 Client ID (type: Web application)
3. Add to **Authorized JavaScript origins:**
   - `http://localhost:3000`
4. Add to **Authorized redirect URIs:**
   - `https://<your-project-ref>.supabase.co/auth/v1/callback`
5. Copy Client ID and Client Secret
6. In Supabase Dashboard, go to **Authentication > Providers > Google**:
   - Enable Google provider
   - Paste Client ID and Client Secret

## Quick start

```bash
# Configure backend
cp .env.example .env
# Fill in Supabase, Mistral, and tool API keys

# Configure frontend
cp web/.env.example web/.env
# Set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY

# Run with Docker (from project root)
docker compose -f docker/docker-compose.yml up --build -d
# Starts: api, web, worker, redis
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |

### Run locally (without Docker)

```bash
# Backend
uv sync
uv run uvicorn main:app --reload

# Frontend
cd web && npm install && npm run dev
```

## Project structure

```
app/
├── core/          # Config, auth, database, middleware, logging
├── features/      # Domain modules (auth, ...)
├── providers/     # Pluggable adapters (LLM, tools, storage)
└── workers/       # ARQ async jobs
web/               # Vue 3 frontend
docker/            # Dockerfile, Dockerfile.web, docker-compose.yml
supabase/          # Supabase local config
```

## License

TBD
