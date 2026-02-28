-- Schedule blocks table: time-slotted radio blocks linking hosts to broadcast schedules.

CREATE TABLE IF NOT EXISTS schedule_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    host_id UUID NOT NULL REFERENCES hosts(id),
    block_type TEXT NOT NULL CHECK (block_type IN ('bloc_music', 'bloc_talk')),
    name TEXT NOT NULL,
    start_time TIME NOT NULL,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    day_of_week INTEGER CHECK (day_of_week >= 0 AND day_of_week <= 6),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_schedule_blocks_host_id ON schedule_blocks(host_id);
CREATE INDEX idx_schedule_blocks_start_time ON schedule_blocks(start_time);
CREATE INDEX idx_schedule_blocks_user_id ON schedule_blocks(user_id);

-- Reuse existing set_updated_at() trigger function from migration 004
CREATE TRIGGER trg_schedule_blocks_updated_at
    BEFORE UPDATE ON schedule_blocks
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
