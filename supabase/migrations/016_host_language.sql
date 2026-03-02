-- Add per-host language column.
-- This is the host's on-air language: what language the host speaks during
-- broadcasts and what language TTS synthesis uses. Defaults to French ('fr')
-- since Tramontane is a French radio station.

ALTER TABLE hosts ADD COLUMN IF NOT EXISTS language TEXT NOT NULL DEFAULT 'fr';
