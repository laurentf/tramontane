-- Hosts table: AI radio host profiles with avatar, voice, and personality data.

CREATE TABLE IF NOT EXISTS hosts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    template_id TEXT NOT NULL,
    style_description TEXT,
    genre_preference TEXT,
    system_prompt TEXT,
    description TEXT,
    avatar_prompt TEXT,
    avatar_url TEXT,
    avatar_status TEXT NOT NULL DEFAULT 'pending',
    avatar_generation_id TEXT,
    voice_id TEXT,
    voice_name TEXT,
    voice_settings JSONB DEFAULT '{}',
    test_phrase TEXT,
    test_phrase_audio_url TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_hosts_user_id ON hosts(user_id);
CREATE INDEX idx_hosts_status ON hosts(status);

-- Reuse existing set_updated_at() trigger function from migration 004
CREATE TRIGGER trg_hosts_updated_at
    BEFORE UPDATE ON hosts
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
