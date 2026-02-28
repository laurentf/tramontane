-- Replace duration_minutes with end_time for a more natural calendar-style schedule.
-- Existing blocks are migrated by computing end_time from start_time + duration.

ALTER TABLE schedule_blocks ADD COLUMN end_time TIME;

UPDATE schedule_blocks
SET end_time = start_time + (duration_minutes || ' minutes')::interval;

ALTER TABLE schedule_blocks ALTER COLUMN end_time SET NOT NULL;
ALTER TABLE schedule_blocks DROP COLUMN duration_minutes;

ALTER TABLE schedule_blocks
ADD CONSTRAINT check_end_after_start CHECK (end_time > start_time);
