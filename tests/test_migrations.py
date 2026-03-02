"""Tests for database migration SQL files.

Static SQL parse tests that verify DDL structure without a live database.
"""

import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent.parent / "supabase" / "migrations"


class TestPgvectorMigration:
    """Tests for 015_pgvector_tracks.sql."""

    def setup_method(self) -> None:
        self.sql = (MIGRATIONS_DIR / "015_pgvector_tracks.sql").read_text()

    def test_enables_pgvector_extension(self) -> None:
        assert "CREATE EXTENSION" in self.sql
        assert "vector" in self.sql.lower()

    def test_adds_embedding_column_vector_1024(self) -> None:
        assert "embedding" in self.sql
        assert "vector(1024)" in self.sql

    def test_creates_hnsw_index(self) -> None:
        assert "idx_tracks_embedding" in self.sql
        assert "hnsw" in self.sql.lower()
        assert "vector_cosine_ops" in self.sql


class TestHostLanguageMigration:
    """Tests for 016_host_language.sql."""

    def setup_method(self) -> None:
        self.sql = (MIGRATIONS_DIR / "016_host_language.sql").read_text()

    def test_adds_language_column(self) -> None:
        sql_upper = self.sql.upper().replace("  ", " ")
        assert "ALTER TABLE HOSTS" in sql_upper
        assert "language" in self.sql.lower()

    def test_default_is_fr(self) -> None:
        assert "'fr'" in self.sql


class TestPlayHistoryMigration:
    """Tests for 017_play_history.sql."""

    def setup_method(self) -> None:
        self.sql = (MIGRATIONS_DIR / "017_play_history.sql").read_text()

    def test_creates_play_history_table(self) -> None:
        assert "CREATE TABLE" in self.sql.upper()
        assert "play_history" in self.sql

    def test_has_required_columns(self) -> None:
        sql_lower = self.sql.lower()
        for col in ["id", "track_id", "block_id", "host_id", "played_at"]:
            assert col in sql_lower, f"Missing column: {col}"

    def test_has_track_id_foreign_key(self) -> None:
        assert "REFERENCES tracks" in self.sql

    def test_has_host_played_at_index(self) -> None:
        # Index on (host_id, played_at) for rolling window queries
        pattern = re.compile(r"CREATE\s+INDEX.*host_id.*played_at", re.IGNORECASE | re.DOTALL)
        assert pattern.search(self.sql), "Missing index on (host_id, played_at)"

    def test_has_track_played_at_index(self) -> None:
        # Index on (track_id, played_at) for per-track history
        pattern = re.compile(r"CREATE\s+INDEX.*track_id.*played_at", re.IGNORECASE | re.DOTALL)
        assert pattern.search(self.sql), "Missing index on (track_id, played_at)"

    def test_on_delete_cascade_for_track(self) -> None:
        # track_id should CASCADE on delete
        assert "ON DELETE CASCADE" in self.sql.upper()

    def test_on_delete_set_null_for_host_and_block(self) -> None:
        # host_id and block_id should SET NULL on delete
        assert "ON DELETE SET NULL" in self.sql.upper()
