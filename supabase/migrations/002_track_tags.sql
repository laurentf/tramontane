-- Migrate tracks to use many-to-many tags instead of single genre/mood columns.

-- Create track_tags table
CREATE TABLE IF NOT EXISTS track_tags (
    track_id UUID NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'genre',  -- genre, mood, theme, energy, era, etc.
    source TEXT NOT NULL DEFAULT 'id3',       -- id3, user, llm
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (track_id, tag, category)
);

CREATE INDEX idx_track_tags_tag ON track_tags(tag);
CREATE INDEX idx_track_tags_category ON track_tags(category);
CREATE INDEX idx_track_tags_track_id ON track_tags(track_id);

-- Migrate existing genre/mood data into track_tags
INSERT INTO track_tags (track_id, tag, category, source)
SELECT id, LOWER(TRIM(genre)), 'genre', 'id3'
FROM tracks
WHERE genre IS NOT NULL AND TRIM(genre) != ''
ON CONFLICT DO NOTHING;

INSERT INTO track_tags (track_id, tag, category, source)
SELECT id, LOWER(TRIM(mood)), 'mood', 'id3'
FROM tracks
WHERE mood IS NOT NULL AND TRIM(mood) != ''
ON CONFLICT DO NOTHING;

-- Drop old columns
ALTER TABLE tracks DROP COLUMN IF EXISTS genre;
ALTER TABLE tracks DROP COLUMN IF EXISTS mood;
ALTER TABLE tracks DROP COLUMN IF EXISTS album_art_path;
ALTER TABLE tracks DROP COLUMN IF EXISTS ingested_at;

DROP INDEX IF EXISTS idx_tracks_genre;
DROP INDEX IF EXISTS idx_tracks_mood;
