-- Enable Row-Level Security on tracks and track_tags.
-- Writes go through asyncpg with the service role (bypasses RLS).
-- These policies govern access via the Supabase client / PostgREST.

-- tracks ---------------------------------------------------------------
ALTER TABLE tracks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read tracks"
    ON tracks FOR SELECT
    USING (true);

CREATE POLICY "Service role can insert tracks"
    ON tracks FOR INSERT
    WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Service role can update tracks"
    ON tracks FOR UPDATE
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role can delete tracks"
    ON tracks FOR DELETE
    USING (auth.role() = 'service_role');

-- track_tags -----------------------------------------------------------
ALTER TABLE track_tags ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read track_tags"
    ON track_tags FOR SELECT
    USING (true);

CREATE POLICY "Service role can insert track_tags"
    ON track_tags FOR INSERT
    WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Service role can update track_tags"
    ON track_tags FOR UPDATE
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role can delete track_tags"
    ON track_tags FOR DELETE
    USING (auth.role() = 'service_role');
