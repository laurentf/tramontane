"""Music selector -- pgvector semantic search + LLM-driven track curation.

Selects the next track for playback using embedding similarity (if available),
filters by play history for repeat avoidance, and optionally lets the LLM
curate the final pick from a candidate shortlist.
"""

import json
import re
from typing import Any

import structlog

from app.features.content.schemas.content import MusicSelection

logger = structlog.get_logger(__name__)


async def select_next_track(
    pool,
    *,
    block_description: str,
    previous_track_ids: list[str],
    embedding_adapter: Any | None = None,
    llm: Any | None = None,
    model: str | None = None,
) -> MusicSelection | None:
    """Select the next track for playback.

    Strategy:
    1. If embedding_adapter available: pgvector cosine similarity on block_description
    2. Fallback: least-played + random ordering
    3. If LLM available: let LLM pick best from candidates
    4. Otherwise: top candidate wins

    Args:
        pool: asyncpg connection pool.
        block_description: Creative direction for the block (used for embedding query).
        previous_track_ids: Track IDs to exclude (rolling window repeat avoidance).
        embedding_adapter: Optional embedding adapter with embed(texts) method.
        llm: Optional LLM adapter for intelligent curation.
        model: Optional model override for LLM.

    Returns:
        MusicSelection or None if no tracks available.
    """
    candidates = await _fetch_candidates(
        pool,
        block_description=block_description,
        previous_track_ids=previous_track_ids,
        embedding_adapter=embedding_adapter,
    )

    if not candidates:
        logger.warning("music_selector.no_candidates", block_description=block_description)
        return None

    # LLM curation if available
    if llm is not None:
        selected = await _llm_curate(llm, candidates, block_description, model=model)
        if selected:
            return selected

    # Default: pick the top candidate
    track = candidates[0]
    return MusicSelection(
        track_id=str(track["id"]),
        title=track["title"],
        artist=track["artist"],
        file_path=track["file_path"],
        reason="Top candidate by similarity" if embedding_adapter else "Selected by play count and randomness",
        duration_seconds=track.get("duration_seconds"),
    )


async def _fetch_candidates(
    pool,
    *,
    block_description: str,
    previous_track_ids: list[str],
    embedding_adapter: Any | None = None,
) -> list[dict]:
    """Fetch track candidates from the database.

    Uses pgvector similarity if embedding adapter is available,
    otherwise falls back to play_count + random ordering.
    """
    async with pool.acquire(timeout=10) as conn:
        if embedding_adapter is not None:
            try:
                embeddings = await embedding_adapter.embed([block_description])
                query_vector = embeddings[0]
                vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

                rows = await conn.fetch(
                    """
                    SELECT t.id, t.title, t.artist, t.file_path, t.duration_seconds,
                           COALESCE(string_agg(DISTINCT g.tag, ', ') FILTER (WHERE g.category = 'genre'), '') AS genre,
                           COALESCE(string_agg(DISTINCT m.tag, ', ') FILTER (WHERE m.category = 'mood'), '') AS mood,
                           1 - (t.embedding <=> $1::vector) AS similarity
                    FROM tracks t
                    LEFT JOIN track_tags g ON g.track_id = t.id AND g.category = 'genre'
                    LEFT JOIN track_tags m ON m.track_id = t.id AND m.category = 'mood'
                    WHERE t.embedding IS NOT NULL
                      AND t.id != ALL($2::uuid[])
                    GROUP BY t.id
                    ORDER BY t.embedding <=> $1::vector
                    LIMIT 20
                    """,
                    vector_str,
                    previous_track_ids,
                )

                if rows:
                    logger.info(
                        "music_selector.pgvector_candidates",
                        count=len(rows),
                        top_similarity=float(rows[0].get("similarity", 0)),
                    )
                    return [dict(r) for r in rows]
            except Exception:
                logger.exception("music_selector.embedding_query_error")

        # Fallback: least-played + random
        rows = await conn.fetch(
            """
            SELECT t.id, t.title, t.artist, t.file_path, t.duration_seconds,
                   COALESCE(string_agg(DISTINCT g.tag, ', ') FILTER (WHERE g.category = 'genre'), '') AS genre,
                   COALESCE(string_agg(DISTINCT m.tag, ', ') FILTER (WHERE m.category = 'mood'), '') AS mood
            FROM tracks t
            LEFT JOIN track_tags g ON g.track_id = t.id AND g.category = 'genre'
            LEFT JOIN track_tags m ON m.track_id = t.id AND m.category = 'mood'
            WHERE t.id != ALL($1::uuid[])
            GROUP BY t.id
            ORDER BY t.play_count ASC, random()
            LIMIT 10
            """,
            previous_track_ids,
        )

        logger.info("music_selector.fallback_candidates", count=len(rows))
        return [dict(r) for r in rows]


async def _llm_curate(
    llm,
    candidates: list[dict],
    block_description: str,
    *,
    model: str | None = None,
) -> MusicSelection | None:
    """Let the LLM pick the best track from candidates.

    Asks the LLM to consider genre, mood, energy arc, and variety.
    """
    from app.providers.ai_models import AIMessage, MessageRole

    candidate_text = "\n".join(
        f"- ID: {c['id']} | {c['title']} by {c['artist']} | genre: {c.get('genre', '?')} | mood: {c.get('mood', '?')}"
        for c in candidates
    )

    messages = [
        AIMessage(
            role=MessageRole.SYSTEM,
            content="You are a music curator for a radio station. Pick the best track from the candidates.",
        ),
        AIMessage(
            role=MessageRole.USER,
            content=(
                f"Block description: {block_description}\n\n"
                f"Candidates:\n{candidate_text}\n\n"
                "Pick the best track considering genre, mood, energy arc, and variety. "
                'Return JSON: {"track_id": "<uuid>", "reason": "<brief reason>"}'
            ),
        ),
    ]

    try:
        response = await llm.generate(messages, model=model, temperature=0.5, max_tokens=300)
        raw = response.content.strip()
        # Strip markdown code fences (closed or truncated)
        fence_match = re.search(r"```(?:json)?\s*(.*?)(?:\s*```|$)", raw, re.DOTALL)
        if fence_match:
            raw = fence_match.group(1).strip()
        data = json.loads(raw)
        track_id = str(data["track_id"])
        reason = data.get("reason", "LLM selected")

        # Find matching candidate
        for c in candidates:
            if str(c["id"]) == track_id:
                return MusicSelection(
                    track_id=track_id,
                    title=c["title"],
                    artist=c["artist"],
                    file_path=c["file_path"],
                    reason=reason,
                    duration_seconds=c.get("duration_seconds"),
                )

        logger.warning("music_selector.llm_track_not_found", track_id=track_id)
    except Exception:
        logger.exception("music_selector.llm_curation_error")

    return None
