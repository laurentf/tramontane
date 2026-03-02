-- Play history for rolling-window repeat avoidance.
-- Records every track play per block/host for music curation queries.

CREATE TABLE IF NOT EXISTS play_history (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    track_id    UUID NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    block_id    UUID REFERENCES schedule_blocks(id) ON DELETE SET NULL,
    host_id     UUID REFERENCES hosts(id) ON DELETE SET NULL,
    played_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Rolling-window lookups: "what has this host played recently?"
CREATE INDEX IF NOT EXISTS idx_play_history_host_played
    ON play_history (host_id, played_at DESC);

-- Per-track history: "when was this track last played?"
CREATE INDEX IF NOT EXISTS idx_play_history_track_played
    ON play_history (track_id, played_at DESC);
