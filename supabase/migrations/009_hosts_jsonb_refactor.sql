-- 009: Refactor hosts table for JSONB description system
-- Converts description from TEXT to JSONB (stores form fields + enrichment),
-- simplifies voice (fixed per template), drops unused columns.

-- 1. Convert description TEXT -> JSONB
ALTER TABLE hosts ALTER COLUMN description TYPE JSONB USING '{}'::jsonb;
ALTER TABLE hosts ALTER COLUMN description SET DEFAULT '{}'::jsonb;

-- 2. Add voice_provider column
ALTER TABLE hosts ADD COLUMN IF NOT EXISTS voice_provider TEXT DEFAULT 'elevenlabs';

-- 3. Drop columns no longer needed
ALTER TABLE hosts DROP COLUMN IF EXISTS style_description;
ALTER TABLE hosts DROP COLUMN IF EXISTS genre_preference;
ALTER TABLE hosts DROP COLUMN IF EXISTS voice_name;
ALTER TABLE hosts DROP COLUMN IF EXISTS voice_settings;
ALTER TABLE hosts DROP COLUMN IF EXISTS test_phrase;
ALTER TABLE hosts DROP COLUMN IF EXISTS test_phrase_audio_url;
