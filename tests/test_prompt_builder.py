"""Unit tests for prompt builder and content schemas."""

import pytest

from app.features.content.schemas.content import (
    BlockContext,
    ContentSegment,
    ContentSegmentType,
    MusicSelection,
    TransitionScript,
)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_HOST = {
    "name": "DJ Luna",
    "language": "fr",
    "description": {
        "self_description": "I am DJ Luna, queen of the midnight airwaves.",
    },
}

SAMPLE_HOST_NO_DESC = {
    "name": "Ghost DJ",
    "description": {},
}

SAMPLE_TEMPLATE_DATA = {
    "prompt_templates": {
        "core_identity_template": (
            "You are {name}, a radio host on Tramontane Radio. "
            "{core_identity} You broadcast in {language}."
        ),
        "output_format_voice": (
            "OUTPUT FORMAT -- VOICE MODE: Use short, natural sentences."
        ),
        "output_format_text": "ABSOLUTE FORMATTING RULE.",
        "greeting_prompt": "You are opening your radio show. Welcome listeners.",
        "show_intro_template": "You are introducing a new segment of your show.",
        "track_intro_template": "You are about to play the next track.",
        "fallback_identity": "You are a chill radio DJ on Tramontane Radio.",
    },
}

SAMPLE_CONTEXT = BlockContext(
    time_of_day="evening",
    block_description="Laid-back jazz evening",
    previous_tracks=["Blue in Green by Miles Davis", "Take Five by Dave Brubeck"],
    is_block_start=True,
    host_language="fr",
)


# ---------------------------------------------------------------------------
# Content schema tests
# ---------------------------------------------------------------------------


class TestContentSchemas:
    """Test that content schemas are importable and well-formed."""

    def test_content_segment_type_values(self) -> None:
        assert ContentSegmentType.TRACK_INTRO == "TRACK_INTRO"
        assert ContentSegmentType.SHOW_INTRO == "SHOW_INTRO"
        assert ContentSegmentType.GREETING == "GREETING"
        assert ContentSegmentType.TRANSITION == "TRANSITION"
        assert ContentSegmentType.BUMPER == "BUMPER"

    def test_music_selection_schema(self) -> None:
        ms = MusicSelection(
            track_id="abc-123",
            title="Blue in Green",
            artist="Miles Davis",
            file_path="/music/library/blue_in_green.mp3",
            reason="Perfect for the late-night jazz vibe",
        )
        assert ms.title == "Blue in Green"

    def test_transition_script_schema(self) -> None:
        ts = TransitionScript(
            text="And now, something smooth...",
            segment_type=ContentSegmentType.TRANSITION,
            estimated_duration_seconds=12.5,
        )
        assert ts.segment_type == ContentSegmentType.TRANSITION

    def test_block_context_schema(self) -> None:
        ctx = BlockContext(
            time_of_day="morning",
            block_description="Upbeat start",
            previous_tracks=[],
            is_block_start=True,
            host_language="en",
        )
        assert ctx.is_block_start is True


# ---------------------------------------------------------------------------
# Prompt builder tests
# ---------------------------------------------------------------------------


class TestBuildHostPrompt:
    """Tests for build_host_prompt function."""

    def test_assembles_system_prompt_with_core_identity(self) -> None:
        from app.features.content.services.prompt_builder import build_host_prompt

        result = build_host_prompt(SAMPLE_HOST, SAMPLE_TEMPLATE_DATA, SAMPLE_CONTEXT)

        assert "DJ Luna" in result
        assert "queen of the midnight airwaves" in result
        assert "fr" in result

    def test_appends_output_format_voice(self) -> None:
        from app.features.content.services.prompt_builder import build_host_prompt

        result = build_host_prompt(SAMPLE_HOST, SAMPLE_TEMPLATE_DATA, SAMPLE_CONTEXT)

        assert "OUTPUT FORMAT -- VOICE MODE" in result

    def test_injects_context_variables(self) -> None:
        from app.features.content.services.prompt_builder import build_host_prompt

        result = build_host_prompt(SAMPLE_HOST, SAMPLE_TEMPLATE_DATA, SAMPLE_CONTEXT)

        assert "evening" in result
        assert "Laid-back jazz evening" in result

    def test_includes_previous_tracks(self) -> None:
        from app.features.content.services.prompt_builder import build_host_prompt

        result = build_host_prompt(SAMPLE_HOST, SAMPLE_TEMPLATE_DATA, SAMPLE_CONTEXT)

        assert "Blue in Green by Miles Davis" in result
        assert "Take Five by Dave Brubeck" in result

    def test_omits_previous_tracks_when_empty(self) -> None:
        from app.features.content.services.prompt_builder import build_host_prompt

        ctx = BlockContext(
            time_of_day="morning",
            block_description="Test block",
            previous_tracks=[],
            is_block_start=False,
            host_language="fr",
        )
        result = build_host_prompt(SAMPLE_HOST, SAMPLE_TEMPLATE_DATA, ctx)

        assert "Previous tracks" not in result

    def test_appends_skill_prompts(self) -> None:
        from app.features.content.services.prompt_builder import get_segment_prompt
        from app.features.content.schemas.content import ContentSegmentType

        context_data = [
            "CURRENT WEATHER: Montpellier, FR: 18°C, Clear sky.",
            "LATEST NEWS:\n- Headline about something important.",
        ]
        result = get_segment_prompt(
            SAMPLE_TEMPLATE_DATA,
            ContentSegmentType.BLOCK_OPENING,
            context_data=context_data,
        )

        assert "CURRENT WEATHER" in result
        assert "LATEST NEWS" in result

    def test_uses_fallback_identity_when_no_self_description(self) -> None:
        from app.features.content.services.prompt_builder import build_host_prompt

        result = build_host_prompt(SAMPLE_HOST_NO_DESC, SAMPLE_TEMPLATE_DATA, SAMPLE_CONTEXT)

        assert "chill radio DJ on Tramontane Radio" in result


class TestGetSegmentPrompt:
    """Tests for get_segment_prompt function."""

    def test_greeting_maps_to_greeting_prompt(self) -> None:
        from app.features.content.services.prompt_builder import get_segment_prompt

        result = get_segment_prompt(SAMPLE_TEMPLATE_DATA, ContentSegmentType.GREETING)
        assert "opening your radio show" in result

    def test_show_intro_maps_to_show_intro_template(self) -> None:
        from app.features.content.services.prompt_builder import get_segment_prompt

        result = get_segment_prompt(SAMPLE_TEMPLATE_DATA, ContentSegmentType.SHOW_INTRO)
        assert "introducing a new segment" in result

    def test_track_intro_maps_to_track_intro_template(self) -> None:
        from app.features.content.services.prompt_builder import get_segment_prompt

        result = get_segment_prompt(SAMPLE_TEMPLATE_DATA, ContentSegmentType.TRACK_INTRO)
        assert "play the next track" in result

    def test_appends_track_info_when_provided(self) -> None:
        from app.features.content.services.prompt_builder import get_segment_prompt

        result = get_segment_prompt(
            SAMPLE_TEMPLATE_DATA,
            ContentSegmentType.TRACK_INTRO,
            track_info={"title": "So What", "artist": "Miles Davis"},
        )
        assert "So What" in result
        assert "Miles Davis" in result

    def test_appends_previous_track_when_provided(self) -> None:
        from app.features.content.services.prompt_builder import get_segment_prompt

        result = get_segment_prompt(
            SAMPLE_TEMPLATE_DATA,
            ContentSegmentType.TRANSITION,
            previous_track={"title": "Take Five", "artist": "Dave Brubeck"},
        )
        assert "Take Five" in result
        assert "Dave Brubeck" in result


# ---------------------------------------------------------------------------
# Play history repository tests
# ---------------------------------------------------------------------------


class TestPlayHistoryRepository:
    """Tests for PlayHistoryRepository (mocked pool)."""

    async def test_get_recent_track_ids_returns_list(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from app.features.content.repositories.play_history import PlayHistoryRepository

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"track_id": "id-1"},
                {"track_id": "id-2"},
                {"track_id": "id-3"},
            ]
        )
        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=mock_conn)
        mock_pool.acquire().__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire().__aexit__ = AsyncMock(return_value=None)

        repo = PlayHistoryRepository(mock_pool)
        result = await repo.get_recent_track_ids(limit=20)

        assert result == ["id-1", "id-2", "id-3"]


# ---------------------------------------------------------------------------
# Embedding ingest tests
# ---------------------------------------------------------------------------


class TestEmbeddingIngest:
    """Tests for embed_tracks_batch function."""

    async def test_embeds_tracks_with_null_embedding(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from app.features.content.services.embedding_ingest import embed_tracks_batch

        mock_conn = AsyncMock()
        # Return tracks with NULL embedding
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"id": "t1", "title": "Track 1", "artist": "Artist 1", "genre": "jazz", "mood": "chill"},
                {"id": "t2", "title": "Track 2", "artist": "Artist 2", "genre": "rock", "mood": "energetic"},
            ]
        )
        mock_conn.execute = AsyncMock()

        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=mock_conn)
        mock_pool.acquire().__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire().__aexit__ = AsyncMock(return_value=None)

        mock_adapter = AsyncMock()
        # Return 2 embeddings (one per track)
        mock_adapter.embed = AsyncMock(return_value=[[0.1] * 1024, [0.2] * 1024])

        count = await embed_tracks_batch(mock_pool, mock_adapter, batch_size=50)

        assert count == 2
        mock_adapter.embed.assert_called_once()

    async def test_skips_tracks_with_existing_embeddings(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from app.features.content.services.embedding_ingest import embed_tracks_batch

        mock_conn = AsyncMock()
        # No tracks with NULL embedding
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=mock_conn)
        mock_pool.acquire().__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire().__aexit__ = AsyncMock(return_value=None)

        mock_adapter = AsyncMock()

        count = await embed_tracks_batch(mock_pool, mock_adapter, batch_size=50)

        assert count == 0
        mock_adapter.embed.assert_not_called()

    async def test_processes_in_configurable_batch_size(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from app.features.content.services.embedding_ingest import embed_tracks_batch

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"id": f"t{i}", "title": f"Track {i}", "artist": "Artist", "genre": "pop", "mood": "happy"}
                for i in range(3)
            ]
        )
        mock_conn.execute = AsyncMock()

        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=mock_conn)
        mock_pool.acquire().__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire().__aexit__ = AsyncMock(return_value=None)

        mock_adapter = AsyncMock()
        mock_adapter.embed = AsyncMock(return_value=[[0.1] * 1024] * 3)

        count = await embed_tracks_batch(mock_pool, mock_adapter, batch_size=10)

        assert count == 3
        # The SQL query uses the batch_size as LIMIT
        call_args = mock_conn.fetch.call_args
        assert "10" in str(call_args) or 10 in [
            a for a in call_args[0] if isinstance(a, int)
        ] or any(a == 10 for a in call_args[0][1:] if isinstance(a, int))
