-- 011: Re-add voice_provider column (dropped in 010, needed for multi-provider support).
ALTER TABLE hosts ADD COLUMN IF NOT EXISTS voice_provider TEXT NOT NULL DEFAULT 'elevenlabs';
