"""Batch embedding ingest for tracks.

Embeds tracks with NULL embedding columns using the Mistral embedding adapter
and updates them in the database. Can be run as an ARQ task or called directly.
"""

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def embed_tracks_batch(
    pool,
    embedding_adapter,
    *,
    batch_size: int = 50,
) -> int:
    """Embed tracks with NULL embedding and update them in the database.

    Args:
        pool: asyncpg connection pool.
        embedding_adapter: Embedding adapter with embed(texts) method.
        batch_size: Number of tracks to process per batch.

    Returns:
        Total number of tracks embedded.
    """
    total_embedded = 0

    async with pool.acquire(timeout=10) as conn:
        # Fetch tracks with NULL embedding
        rows = await conn.fetch(
            """
            SELECT t.id, t.title, t.artist,
                   COALESCE(string_agg(DISTINCT g.tag, ', ') FILTER (WHERE g.category = 'genre'), 'unknown') AS genre,
                   COALESCE(string_agg(DISTINCT m.tag, ', ') FILTER (WHERE m.category = 'mood'), 'unknown') AS mood
            FROM tracks t
            LEFT JOIN track_tags g ON g.track_id = t.id AND g.category = 'genre'
            LEFT JOIN track_tags m ON m.track_id = t.id AND m.category = 'mood'
            WHERE t.embedding IS NULL
            GROUP BY t.id, t.title, t.artist
            LIMIT $1
            """,
            batch_size,
        )

        if not rows:
            logger.info("embed_tracks.no_tracks", msg="No tracks with NULL embedding")
            return 0

        logger.info("embed_tracks.batch_start", count=len(rows), batch_size=batch_size)

        # Build text representations for embedding
        texts = []
        track_ids = []
        for row in rows:
            text = (
                f"{row['title']} by {row['artist']}"
                f" | genre: {row['genre']}"
                f" | mood: {row['mood']}"
            )
            texts.append(text)
            track_ids.append(row["id"])

        try:
            embeddings = await embedding_adapter.embed(texts)
        except Exception:
            logger.exception("embed_tracks.embed_error", count=len(texts))
            return 0

        # Update each track with its embedding
        for track_id, embedding in zip(track_ids, embeddings):
            embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
            await conn.execute(
                "UPDATE tracks SET embedding = $1::vector WHERE id = $2",
                embedding_str,
                track_id,
            )
            total_embedded += 1

        logger.info("embed_tracks.batch_complete", embedded=total_embedded)

    return total_embedded


async def embed_tracks_task(ctx: dict[str, Any]) -> int:
    """ARQ task wrapper for batch track embedding.

    Args:
        ctx: ARQ worker context with 'pool' key.

    Returns:
        Number of tracks embedded.
    """
    from app.core.config import get_settings
    from app.providers.embedding.mistral.adapter import MistralEmbeddingAdapter

    pool = ctx["pool"]
    settings = get_settings()

    if not settings.mistral_api_key:
        logger.warning("embed_tracks_task.no_api_key", msg="Mistral API key not set, skipping")
        return 0

    adapter = MistralEmbeddingAdapter(api_key=settings.mistral_api_key.get_secret_value())
    return await embed_tracks_batch(pool, adapter)
