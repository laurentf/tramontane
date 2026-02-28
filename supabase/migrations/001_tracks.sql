CREATE TABLE IF NOT EXISTS tracks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL DEFAULT 'Unknown Title',
    artist TEXT NOT NULL DEFAULT 'Unknown Artist',
    album TEXT DEFAULT NULL,
    genre TEXT DEFAULT NULL,
    mood TEXT DEFAULT NULL,
    duration_seconds FLOAT DEFAULT NULL,
    file_path TEXT NOT NULL UNIQUE,
    file_size_bytes BIGINT DEFAULT NULL,
    album_art_path TEXT DEFAULT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    play_count INTEGER NOT NULL DEFAULT 0,
    last_played_at TIMESTAMPTZ DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tracks_genre ON tracks(genre);
CREATE INDEX idx_tracks_mood ON tracks(mood);
CREATE INDEX idx_tracks_artist ON tracks(artist);
