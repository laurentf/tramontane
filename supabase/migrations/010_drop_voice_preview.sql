-- 010: Drop voice preview and system_prompt columns
ALTER TABLE hosts DROP COLUMN IF EXISTS system_prompt;
ALTER TABLE hosts DROP COLUMN IF EXISTS voice_provider;
