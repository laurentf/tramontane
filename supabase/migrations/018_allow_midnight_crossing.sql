-- Allow schedule blocks that cross midnight (e.g. 23:00 -> 00:00)
ALTER TABLE schedule_blocks
DROP CONSTRAINT check_end_after_start;

ALTER TABLE schedule_blocks
ADD CONSTRAINT check_times_differ CHECK (end_time != start_time);
