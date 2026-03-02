"""Tests for schedule engine v2 -- buffer-aware queue management with block boundaries."""

import time
from datetime import time as dt_time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.features.content.schemas.content import ContentSegmentType


# ---------------------------------------------------------------------------
# Schedule Repository: get_by_id_unscoped + new methods
# ---------------------------------------------------------------------------


class TestScheduleRepositoryUnscoped:
    """Tests for ScheduleRepository.get_by_id_unscoped."""

    @pytest.fixture
    def mock_pool(self):
        pool = MagicMock()
        conn = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__.return_value = conn
        cm.__aexit__.return_value = False
        pool.acquire.return_value = cm
        return pool, conn

    async def test_get_by_id_unscoped_returns_block(self, mock_pool):
        from app.features.schedule.repositories.schedule_repository import ScheduleRepository

        pool, conn = mock_pool
        conn.fetchrow.return_value = {
            "id": "block-1",
            "host_id": "host-1",
            "name": "Jazz Hour",
            "description": "Evening jazz",
            "start_time": "20:00",
            "end_time": "22:00",
        }

        repo = ScheduleRepository(pool)
        result = await repo.get_by_id_unscoped("block-1")

        assert result is not None
        assert result["id"] == "block-1"
        assert result["name"] == "Jazz Hour"
        call_args = conn.fetchrow.call_args
        assert len(call_args.args) == 2  # query + block_id only

    async def test_get_by_id_unscoped_returns_none(self, mock_pool):
        from app.features.schedule.repositories.schedule_repository import ScheduleRepository

        pool, conn = mock_pool
        conn.fetchrow.return_value = None

        repo = ScheduleRepository(pool)
        result = await repo.get_by_id_unscoped("nonexistent-block")
        assert result is None


class TestScheduleRepositoryAdjacentBlocks:
    """Tests for get_next_block and get_previous_block."""

    @pytest.fixture
    def mock_pool(self):
        pool = MagicMock()
        conn = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__.return_value = conn
        cm.__aexit__.return_value = False
        pool.acquire.return_value = cm
        return pool, conn

    async def test_get_next_block_returns_block(self, mock_pool):
        from app.features.schedule.repositories.schedule_repository import ScheduleRepository

        pool, conn = mock_pool
        conn.fetchrow.return_value = {
            "id": "block-2",
            "host_id": "host-2",
            "host_name": "MC Groove",
            "start_time": "14:00",
            "end_time": "16:00",
        }

        repo = ScheduleRepository(pool)
        result = await repo.get_next_block("14:00")

        assert result is not None
        assert result["host_name"] == "MC Groove"

    async def test_get_next_block_returns_none(self, mock_pool):
        from app.features.schedule.repositories.schedule_repository import ScheduleRepository

        pool, conn = mock_pool
        conn.fetchrow.return_value = None

        repo = ScheduleRepository(pool)
        result = await repo.get_next_block("23:00")
        assert result is None

    async def test_get_previous_block_returns_block(self, mock_pool):
        from app.features.schedule.repositories.schedule_repository import ScheduleRepository

        pool, conn = mock_pool
        conn.fetchrow.return_value = {
            "id": "block-1",
            "host_id": "host-1",
            "host_name": "DJ Chill",
            "start_time": "10:00",
            "end_time": "12:00",
        }

        repo = ScheduleRepository(pool)
        result = await repo.get_previous_block("12:00")

        assert result is not None
        assert result["host_name"] == "DJ Chill"

    async def test_get_previous_block_returns_none(self, mock_pool):
        from app.features.schedule.repositories.schedule_repository import ScheduleRepository

        pool, conn = mock_pool
        conn.fetchrow.return_value = None

        repo = ScheduleRepository(pool)
        result = await repo.get_previous_block("06:00")
        assert result is None


# ---------------------------------------------------------------------------
# time_diff_seconds helper
# ---------------------------------------------------------------------------


class TestTimeDiffSeconds:
    def test_normal_diff(self):
        from app.features.content.services.schedule_engine import _time_diff_seconds

        assert _time_diff_seconds(dt_time(10, 0), dt_time(12, 0)) == 7200.0

    def test_same_time(self):
        from app.features.content.services.schedule_engine import _time_diff_seconds

        assert _time_diff_seconds(dt_time(10, 0), dt_time(10, 0)) == 0.0

    def test_past_time_floors_at_zero(self):
        from app.features.content.services.schedule_engine import _time_diff_seconds

        assert _time_diff_seconds(dt_time(14, 0), dt_time(12, 0)) == 0.0

    def test_partial_seconds(self):
        from app.features.content.services.schedule_engine import _time_diff_seconds

        # 10:00:30 to 10:01:00 = 30 seconds
        assert _time_diff_seconds(dt_time(10, 0, 30), dt_time(10, 1, 0)) == 30.0


# ---------------------------------------------------------------------------
# Schedule Tick Tests
# ---------------------------------------------------------------------------


class TestScheduleTick:
    """Tests for schedule_engine.schedule_tick (v2 buffer-aware)."""

    @pytest.fixture
    def sample_block(self):
        return {
            "id": "block-1",
            "user_id": "user-1",
            "host_id": "host-1",
            "name": "Jazz Hour",
            "description": "Evening jazz session",
            "start_time": dt_time(20, 0),
            "end_time": dt_time(22, 0),
            "day_of_week": None,
            "is_active": True,
            "host_name": "DJ Chill",
            "host_avatar_url": None,
            "host_template_id": "chill_dj",
            "block_type": "bloc_music",
        }

    async def test_tick_pushes_when_buffer_low(self, sample_block):
        """Pushes content when queue budget is below BUFFER_LOW_SEC."""
        from app.features.content.services.schedule_engine import schedule_tick

        ctx = {
            "pool": MagicMock(),
            "last_tick_ts": time.time(),
            "queue_budget_sec": 0.0,  # empty buffer
            "current_block_id": "block-1",  # not a cold start
        }

        with patch("app.features.content.services.schedule_engine.ScheduleRepository") as MockRepo, \
             patch("app.features.content.services.schedule_engine._push_track_with_voice") as mock_push:
            mock_repo = AsyncMock()
            mock_repo.get_active_block.return_value = sample_block
            MockRepo.return_value = mock_repo
            mock_push.return_value = None

            await schedule_tick(ctx)

            mock_push.assert_called_once()

    async def test_tick_skips_when_buffer_healthy(self, sample_block):
        """Skips push when queue budget is above BUFFER_LOW_SEC."""
        from app.features.content.services.schedule_engine import schedule_tick

        ctx = {
            "pool": MagicMock(),
            "last_tick_ts": time.time(),
            "queue_budget_sec": 200.0,  # plenty of buffer
            "current_block_id": "block-1",  # not a cold start
        }

        with patch("app.features.content.services.schedule_engine.ScheduleRepository") as MockRepo, \
             patch("app.features.content.services.schedule_engine._push_track_with_voice") as mock_push:
            mock_repo = AsyncMock()
            mock_repo.get_active_block.return_value = sample_block
            MockRepo.return_value = mock_repo

            await schedule_tick(ctx)

            mock_push.assert_not_called()

    async def test_tick_resets_on_dead_hour(self):
        """Resets state when no active block (dead-hour awareness)."""
        from app.features.content.services.schedule_engine import schedule_tick

        ctx = {
            "pool": MagicMock(),
            "last_tick_ts": time.time(),
            "queue_budget_sec": 100.0,
            "current_block_id": "old-block",
            "closing_pushed": True,
        }

        with patch("app.features.content.services.schedule_engine.ScheduleRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.get_active_block.return_value = None
            mock_repo.get_upcoming_blocks.return_value = []
            MockRepo.return_value = mock_repo

            await schedule_tick(ctx)

            assert ctx["current_block_id"] is None
            assert ctx["closing_pushed"] is False
            assert ctx["queue_budget_sec"] == 0.0

    async def test_tick_detects_block_transition(self, sample_block):
        """Detects block transition and pushes opening with previous host name."""
        from app.features.content.services.schedule_engine import schedule_tick

        new_block = {**sample_block, "id": "block-2", "host_id": "host-2", "host_name": "MC Groove"}
        ctx = {
            "pool": MagicMock(),
            "last_tick_ts": time.time(),
            "queue_budget_sec": 0.0,
            "current_block_id": "block-1",
        }

        with patch("app.features.content.services.schedule_engine.ScheduleRepository") as MockRepo, \
             patch("app.features.content.services.schedule_engine._push_opening") as mock_opening, \
             patch("app.features.content.services.schedule_engine._push_track_with_voice") as mock_push:
            mock_repo = AsyncMock()
            mock_repo.get_active_block.return_value = new_block
            mock_repo.get_previous_block.return_value = {
                "host_name": "DJ Chill",
                "id": "block-1",
            }
            MockRepo.return_value = mock_repo
            mock_opening.return_value = None
            mock_push.return_value = None

            await schedule_tick(ctx)

            mock_opening.assert_called_once()
            # Verify previous_host_name was passed
            call_kwargs = mock_opening.call_args.kwargs
            assert call_kwargs.get("previous_host_name") == "DJ Chill"

    async def test_tick_closing_window(self, sample_block):
        """Pushes closing + last track when near block end."""
        from app.features.content.services.schedule_engine import schedule_tick, CLOSING_WINDOW_SEC

        # Make block end very soon
        from datetime import datetime, timedelta

        now = datetime.now()
        # Block ends in 45 seconds (< CLOSING_WINDOW_SEC)
        end_soon = (now + timedelta(seconds=45)).time()
        closing_block = {**sample_block, "end_time": end_soon}

        ctx = {
            "pool": MagicMock(),
            "last_tick_ts": time.time(),
            "queue_budget_sec": 10.0,  # budget < block_remaining
            "current_block_id": "block-1",  # same block, no transition
        }

        with patch("app.features.content.services.schedule_engine.ScheduleRepository") as MockRepo, \
             patch("app.features.content.services.schedule_engine._push_closing") as mock_closing, \
             patch("app.features.content.services.schedule_engine._push_track_with_voice") as mock_push:
            mock_repo = AsyncMock()
            mock_repo.get_active_block.return_value = closing_block
            mock_repo.get_next_block.return_value = {
                "host_name": "MC Groove",
                "id": "block-2",
            }
            MockRepo.return_value = mock_repo
            mock_closing.return_value = None
            mock_push.return_value = None

            await schedule_tick(ctx)

            mock_closing.assert_called_once()
            # Verify next_host_name was passed
            call_kwargs = mock_closing.call_args.kwargs
            assert call_kwargs.get("next_host_name") == "MC Groove"
            # Last track pushed after closing
            mock_push.assert_called_once()
            # closing_pushed flag set
            assert ctx["closing_pushed"] is True

    async def test_tick_stops_feeding_after_closing(self, sample_block):
        """Does not push content after closing has been pushed."""
        from app.features.content.services.schedule_engine import schedule_tick

        ctx = {
            "pool": MagicMock(),
            "last_tick_ts": time.time(),
            "queue_budget_sec": 0.0,
            "current_block_id": "block-1",
            "closing_pushed": True,
        }

        with patch("app.features.content.services.schedule_engine.ScheduleRepository") as MockRepo, \
             patch("app.features.content.services.schedule_engine._push_track_with_voice") as mock_push:
            mock_repo = AsyncMock()
            mock_repo.get_active_block.return_value = sample_block
            MockRepo.return_value = mock_repo

            await schedule_tick(ctx)

            mock_push.assert_not_called()

    async def test_tick_drains_budget_by_elapsed(self, sample_block):
        """Budget decreases by elapsed time between ticks."""
        from app.features.content.services.schedule_engine import schedule_tick

        now = time.time()
        ctx = {
            "pool": MagicMock(),
            "last_tick_ts": now - 30,  # 30 seconds ago
            "queue_budget_sec": 200.0,
            "current_block_id": "block-1",  # not a cold start
        }

        with patch("app.features.content.services.schedule_engine.ScheduleRepository") as MockRepo, \
             patch("app.features.content.services.schedule_engine._push_track_with_voice"):
            mock_repo = AsyncMock()
            mock_repo.get_active_block.return_value = sample_block
            MockRepo.return_value = mock_repo

            await schedule_tick(ctx)

            # Budget should have dropped by ~30s
            assert ctx["queue_budget_sec"] < 200.0
            assert ctx["queue_budget_sec"] > 130.0  # roughly 200 - 30 = 170, with some tolerance

    async def test_tick_cold_start_pushes_opening_with_track(self, sample_block):
        """Cold start: calls _do_cold_start when no current_block_id."""
        from app.features.content.services.schedule_engine import schedule_tick

        ctx = {
            "pool": MagicMock(),
            "last_tick_ts": time.time(),
            "queue_budget_sec": 0.0,
            # No current_block_id -- cold start
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # no cold_start_done yet
        ctx["redis"] = mock_redis

        with patch("app.features.content.services.schedule_engine.ScheduleRepository") as MockRepo, \
             patch("app.features.content.services.schedule_engine._do_cold_start") as mock_cold:
            mock_repo = AsyncMock()
            mock_repo.get_active_block.return_value = sample_block
            MockRepo.return_value = mock_repo
            mock_cold.return_value = None

            await schedule_tick(ctx)

            mock_cold.assert_called_once()
            # current_block_id set
            assert ctx["current_block_id"] == "block-1"
            # Redis key set to prevent re-entry
            mock_redis.set.assert_any_call("cold_start_done", "block-1", ex=3600)

    async def test_tick_pre_generates_for_upcoming_block(self, sample_block):
        """Pre-generates content ahead of block start (SCHED-03)."""
        from app.features.content.services.schedule_engine import schedule_tick

        upcoming_block = {**sample_block, "id": "block-upcoming"}
        ctx = {
            "pool": MagicMock(),
            "last_tick_ts": time.time(),
            "queue_budget_sec": 0.0,
        }

        with patch("app.features.content.services.schedule_engine.ScheduleRepository") as MockRepo, \
             patch("app.features.content.services.schedule_engine.arq_enqueue") as mock_enqueue:
            mock_repo = AsyncMock()
            mock_repo.get_active_block.return_value = None
            mock_repo.get_upcoming_blocks.return_value = [upcoming_block]
            MockRepo.return_value = mock_repo
            mock_enqueue.return_value = None

            await schedule_tick(ctx)

            mock_enqueue.assert_called()


# ---------------------------------------------------------------------------
# Generate Content Segment Tests (ARQ entry point)
# ---------------------------------------------------------------------------


class TestGenerateContentSegment:
    """Tests for generate_content_segment (ARQ-registered task)."""

    @pytest.fixture
    def sample_block(self):
        return {
            "id": "block-1",
            "user_id": "user-1",
            "host_id": "host-1",
            "name": "Jazz Hour",
            "description": "Evening jazz session",
            "block_type": "bloc_music",
            "start_time": "20:00:00",
            "end_time": "22:00:00",
            "host_template_id": "chill_dj",
        }

    async def test_routes_to_push_closing(self, sample_block):
        """Routes is_closing=True to _push_closing."""
        from app.features.content.services.schedule_engine import generate_content_segment

        ctx = {"pool": MagicMock()}

        with patch("app.features.content.services.schedule_engine.ScheduleRepository") as MockRepo, \
             patch("app.features.content.services.schedule_engine._push_closing") as mock_closing:
            MockRepo.return_value.get_by_id_unscoped = AsyncMock(return_value=sample_block)
            mock_closing.return_value = None

            await generate_content_segment(ctx, "block-1", is_closing=True)

            mock_closing.assert_called_once()

    async def test_routes_to_push_opening(self, sample_block):
        """Routes is_opening=True to _push_opening."""
        from app.features.content.services.schedule_engine import generate_content_segment

        ctx = {"pool": MagicMock()}

        with patch("app.features.content.services.schedule_engine.ScheduleRepository") as MockRepo, \
             patch("app.features.content.services.schedule_engine._push_opening") as mock_opening:
            MockRepo.return_value.get_by_id_unscoped = AsyncMock(return_value=sample_block)
            mock_opening.return_value = None

            await generate_content_segment(ctx, "block-1", is_opening=True)

            mock_opening.assert_called_once()

    async def test_routes_to_push_track(self, sample_block):
        """Routes normal segment to _push_track_with_voice."""
        from app.features.content.services.schedule_engine import generate_content_segment

        ctx = {"pool": MagicMock()}

        with patch("app.features.content.services.schedule_engine.ScheduleRepository") as MockRepo, \
             patch("app.features.content.services.schedule_engine._push_track_with_voice") as mock_push:
            MockRepo.return_value.get_by_id_unscoped = AsyncMock(return_value=sample_block)
            mock_push.return_value = None

            await generate_content_segment(ctx, "block-1")

            mock_push.assert_called_once()

    async def test_handles_missing_block(self):
        """Returns early if block not found."""
        from app.features.content.services.schedule_engine import generate_content_segment

        ctx = {"pool": MagicMock()}

        with patch("app.features.content.services.schedule_engine.ScheduleRepository") as MockRepo:
            MockRepo.return_value.get_by_id_unscoped = AsyncMock(return_value=None)

            # Should not raise
            await generate_content_segment(ctx, "nonexistent")


# ---------------------------------------------------------------------------
# _push_track_with_voice Tests
# ---------------------------------------------------------------------------


class TestPushTrackWithVoice:
    """Tests for the inline track push with pacing and budget tracking."""

    @pytest.fixture
    def sample_block(self):
        return {
            "id": "block-1",
            "host_id": "host-1",
            "name": "Jazz Hour",
            "description": "Evening jazz",
            "block_type": "bloc_music",
            "host_template_id": "chill_dj",
        }

    @pytest.fixture
    def sample_host(self):
        return {
            "id": "host-1",
            "name": "DJ Chill",
            "language": "en",
            "template_id": "chill_dj",
            "description": {"self_description": "A laid-back DJ"},
            "voice_id": "voice-abc",
        }

    async def test_pushes_track_and_updates_budget(self, sample_block, sample_host):
        """Selects track, pushes it, records play, and updates budget."""
        from app.features.content.services.schedule_engine import _push_track_with_voice

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"1")
        mock_redis.incr = AsyncMock()
        ctx = {"pool": MagicMock(), "redis": mock_redis, "queue_budget_sec": 0.0}

        with patch("app.features.content.services.schedule_engine._load_segment_context") as mock_load, \
             patch("app.features.content.services.schedule_engine.PlayHistoryRepository") as MockPlayHistory, \
             patch("app.features.content.services.schedule_engine._create_llm") as mock_llm, \
             patch("app.features.content.services.schedule_engine._create_tts") as mock_tts, \
             patch("app.features.content.services.schedule_engine._create_embedding") as mock_embed, \
             patch("app.features.content.services.schedule_engine.select_next_track") as mock_select, \
             patch("app.features.content.services.schedule_engine.generate_transition") as mock_transition, \
             patch("app.features.content.services.schedule_engine.push_music_track") as mock_push:
            from app.features.content.schemas.content import BlockContext

            mock_load.return_value = (
                sample_host,
                {"prompt_templates": {}},
                BlockContext(time_of_day="evening", block_description="Jazz"),
            )
            mock_play_history = AsyncMock()
            mock_play_history.get_recent_track_ids.return_value = []
            MockPlayHistory.return_value = mock_play_history
            mock_llm.return_value = AsyncMock()
            mock_tts.return_value = None  # TTS disabled for this test
            mock_embed.return_value = None
            mock_transition.return_value = MagicMock(text="Nice track...")
            mock_select.return_value = MagicMock(
                track_id="track-1", title="Jazz Song", artist="Jazz Cat",
                file_path="/music/library/jazz.mp3", reason="Good fit",
                duration_seconds=195.0,
            )
            mock_push.return_value = True

            await _push_track_with_voice(ctx, MagicMock(), sample_block)

            mock_push.assert_called_once()
            mock_play_history.record_play.assert_called_once()
            mock_transition.assert_called_once()
            # Budget should have increased by track duration
            assert ctx["queue_budget_sec"] == 195.0

    async def test_always_transitions_for_bloc_music(self, sample_block, sample_host):
        """Always generates a transition between tracks for bloc_music."""
        from app.features.content.services.schedule_engine import _push_track_with_voice

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"1")  # any track count
        mock_redis.incr = AsyncMock()
        ctx = {"pool": MagicMock(), "redis": mock_redis, "queue_budget_sec": 0.0}

        with patch("app.features.content.services.schedule_engine._load_segment_context") as mock_load, \
             patch("app.features.content.services.schedule_engine.PlayHistoryRepository") as MockPlayHistory, \
             patch("app.features.content.services.schedule_engine._create_llm") as mock_llm, \
             patch("app.features.content.services.schedule_engine._create_embedding") as mock_embed, \
             patch("app.features.content.services.schedule_engine.select_next_track") as mock_select, \
             patch("app.features.content.services.schedule_engine.generate_transition") as mock_transition, \
             patch("app.features.content.services.schedule_engine.push_music_track") as mock_push:
            from app.features.content.schemas.content import BlockContext

            mock_load.return_value = (
                sample_host,
                {"prompt_templates": {}},
                BlockContext(time_of_day="evening", block_description="Jazz"),
            )
            mock_play_history = AsyncMock()
            mock_play_history.get_recent_track_ids.return_value = []
            MockPlayHistory.return_value = mock_play_history
            mock_llm.return_value = AsyncMock()
            mock_embed.return_value = None
            mock_select.return_value = MagicMock(
                track_id="track-1", title="Jazz Song", artist="Jazz Cat",
                file_path="/music/library/jazz.mp3", reason="Good fit",
                duration_seconds=200.0,
            )
            mock_transition.return_value = MagicMock(text="That was smooth...")
            mock_push.return_value = True

            await _push_track_with_voice(ctx, MagicMock(), sample_block)

            mock_transition.assert_called_once()
            mock_push.assert_called_once()

    async def test_always_transition_for_bloc_talk(self, sample_block, sample_host):
        """Generates transition between every track for bloc_talk blocks."""
        from app.features.content.services.schedule_engine import _push_track_with_voice

        talk_block = {**sample_block, "block_type": "bloc_talk"}
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"1")
        mock_redis.incr = AsyncMock()
        ctx = {"pool": MagicMock(), "redis": mock_redis, "queue_budget_sec": 0.0}

        with patch("app.features.content.services.schedule_engine._load_segment_context") as mock_load, \
             patch("app.features.content.services.schedule_engine.PlayHistoryRepository") as MockPlayHistory, \
             patch("app.features.content.services.schedule_engine._create_llm") as mock_llm, \
             patch("app.features.content.services.schedule_engine._create_embedding") as mock_embed, \
             patch("app.features.content.services.schedule_engine.select_next_track") as mock_select, \
             patch("app.features.content.services.schedule_engine.generate_transition") as mock_transition, \
             patch("app.features.content.services.schedule_engine.push_music_track") as mock_push:
            from app.features.content.schemas.content import BlockContext

            mock_load.return_value = (
                sample_host,
                {"prompt_templates": {}},
                BlockContext(time_of_day="evening", block_description="Talk show"),
            )
            mock_play_history = AsyncMock()
            mock_play_history.get_recent_track_ids.return_value = []
            MockPlayHistory.return_value = mock_play_history
            mock_llm.return_value = AsyncMock()
            mock_embed.return_value = None
            mock_select.return_value = MagicMock(
                track_id="track-1", title="Jazz Song", artist="Jazz Cat",
                file_path="/music/library/jazz.mp3", reason="Good fit",
                duration_seconds=200.0,
            )
            mock_transition.return_value = MagicMock(text="Let me tell you...")
            mock_push.return_value = True

            await _push_track_with_voice(ctx, MagicMock(), talk_block)

            mock_transition.assert_called_once()

    async def test_handles_no_host(self, sample_block):
        """Returns early if host not found."""
        from app.features.content.services.schedule_engine import _push_track_with_voice

        ctx = {"pool": MagicMock(), "queue_budget_sec": 0.0}

        with patch("app.features.content.services.schedule_engine._load_segment_context") as mock_load:
            from app.features.content.schemas.content import BlockContext

            mock_load.return_value = (None, {}, BlockContext(time_of_day="", block_description=""))

            # Should not raise
            await _push_track_with_voice(ctx, MagicMock(), sample_block)
