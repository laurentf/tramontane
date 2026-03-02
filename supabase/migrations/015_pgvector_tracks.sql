-- Enable pgvector extension for semantic track search.
-- Adds embedding column (1024-dimensional, matching mistral-embed output)
-- and HNSW index for efficient cosine similarity queries.

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE tracks ADD COLUMN IF NOT EXISTS embedding vector(1024);

-- HNSW index for cosine similarity nearest-neighbor search.
-- m=16, ef_construction=64 are good defaults for <100K rows.
CREATE INDEX IF NOT EXISTS idx_tracks_embedding
    ON tracks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
