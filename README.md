# Tramontane

Autonomous self-hosted web radio powered by AI.

**Mistral Worldwide Hackathon — February 2026 (Online Edition)**

## What is it

Tramontane is a platform for running AI-driven web radio stations. Define radio hosts with their own personality, background, and style. Set the radio theme, topics of interest, manage planning and scheduling, and let the AI handle interviews, podcasts, and live content autonomously.

## Features

### Audio Pipeline
- Icecast + Liquidsoap streaming with crossfade transitions
- Music ingest pipeline (MP3, FLAC, OGG) with automatic metadata extraction (genre, mood, artist)
- Retro pixel-art web player with visualizer, volume control, and now-playing display
- Fallback source ensures the stream never goes silent
- Track push via Harbor HTTP API

### Host Management
- Personality templates (Chill DJ, Comedy Host, Culture Reviewer, Journalist)
- LLM-powered profile enrichment (Mistral generates personality, description, avatar prompt)
- Leonardo AI avatar generation (async with polling)
- Host management with avatar regeneration (admin) and read-only host profiles (all users)
- Skill system (weather lookup, web search) with YAML manifests and prompt injection

### Schedule
- Schedule block CRUD (music and talk blocks) with time slots
- Overlap validation and host assignment
- Active block detection for now-playing card
- Timeline visualization

### Settings
- Per-user radio settings (station name, language, location)
- i18n support (English, French, Spanish)

### Access Control
- Supabase JWT authentication (Google OAuth)
- Role-based UI: all authenticated users can browse hosts and view host profiles; admin users can create, delete, and regenerate avatars
- Admin-only management: host creation/deletion, schedule, settings, ingest, radio push (configured via `ADMIN_EMAILS`)
- Public endpoints: radio player (now-playing), active schedule block, personality templates

## Stack

- **Backend:** FastAPI + asyncpg + Supabase (auth, DB, storage)
- **Frontend:** Vue 3 + Vite + Tailwind CSS + Pinia
- **AI:** Mistral (LLM, embeddings, STT, analysis)
- **Image:** Leonardo AI (avatar generation)
- **TTS:** ElevenLabs
- **Search:** Tavily
- **Weather:** OpenWeatherMap
- **Streaming:** Icecast + Liquidsoap
- **Workers:** ARQ (Redis-based async job queue)
- **Infra:** Docker Compose

## Prerequisites

### 1. Supabase project

Create a free project at [supabase.com](https://supabase.com):

1. Create a new project
2. Fill in the Supabase env keys in `.env`
3. Use the **transaction pooler** connection string for `DATABASE_URL`
4. Create a **private** storage bucket named `pictures` (used for host avatars)

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

### 3. API keys

| Service | Key | Required |
|---------|-----|----------|
| Mistral | `MISTRAL_API_KEY` | Yes |
| Leonardo AI | `LEONARDO_API_KEY` | For avatar generation |
| ElevenLabs | `ELEVENLABS_API_KEY` | For TTS (Phase 3) |
| Tavily | `TAVILY_API_KEY` | For web search skill |
| OpenWeatherMap | `OPENWEATHER_API_KEY` | For weather skill |
| Admin access | `ADMIN_EMAILS` | JSON list of admin emails, e.g. `["you@example.com"]` |

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
# Starts: api, web, worker, redis, icecast, liquidsoap
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |
| Radio stream | http://localhost:8100/stream.mp3 |

### Run locally (without Docker)

```bash
# Backend
uv sync
uv run uvicorn main:app --reload

# Frontend
cd web && npm install && npm run dev
```

### Add music

Drop MP3/FLAC/OGG files into the `/music/` directory, then scan:

```bash
curl -X POST http://localhost:8000/api/v1/ingest/scan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"directory": "/music"}'
```

Re-run anytime to pick up new files (idempotent upsert).

## Project structure

```
app/
├── core/              # Config, auth, database, middleware, logging
├── features/
│   ├── auth/          # Supabase auth
│   ├── hosts/         # Host CRUD, templates, LLM enrichment, skills
│   ├── ingest/        # Music ingest pipeline
│   ├── radio/         # Streaming API, now-playing, Liquidsoap client
│   ├── schedule/      # Schedule block CRUD, active block detection
│   └── settings/      # Per-user radio settings
├── providers/         # Pluggable adapters (LLM, image, search, weather, TTS, STT)
└── workers/           # ARQ async jobs
web/                   # Vue 3 frontend
docker/                # Dockerfiles, docker-compose, Icecast/Liquidsoap config
supabase/              # Migrations
```

## License

TBD
