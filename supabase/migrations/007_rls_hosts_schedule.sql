-- Enable Row-Level Security on hosts and schedule_blocks.
-- Writes go through asyncpg with the service role (bypasses RLS).
-- These policies govern access via the Supabase client / PostgREST.

-- hosts ---------------------------------------------------------------
ALTER TABLE hosts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read hosts"
    ON hosts FOR SELECT
    USING (true);

CREATE POLICY "Service role can insert hosts"
    ON hosts FOR INSERT
    WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Service role can update hosts"
    ON hosts FOR UPDATE
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role can delete hosts"
    ON hosts FOR DELETE
    USING (auth.role() = 'service_role');

-- schedule_blocks -----------------------------------------------------
ALTER TABLE schedule_blocks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read schedule_blocks"
    ON schedule_blocks FOR SELECT
    USING (true);

CREATE POLICY "Service role can insert schedule_blocks"
    ON schedule_blocks FOR INSERT
    WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Service role can update schedule_blocks"
    ON schedule_blocks FOR UPDATE
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role can delete schedule_blocks"
    ON schedule_blocks FOR DELETE
    USING (auth.role() = 'service_role');
