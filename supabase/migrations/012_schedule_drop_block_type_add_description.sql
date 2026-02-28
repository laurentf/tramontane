-- Remove block_type (music/talk distinction is now driven by host template).
-- Add description (required brief that guides content generation for the slot).

ALTER TABLE schedule_blocks DROP COLUMN block_type;
ALTER TABLE schedule_blocks ADD COLUMN description TEXT NOT NULL DEFAULT '';
