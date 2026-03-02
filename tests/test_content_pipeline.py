"""Tests for content pipeline services: music selector, transition generator, TTS pipeline, bumper generator."""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.features.content.schemas.content import (
    BlockContext,
    ContentSegmentType,
    MusicSelection,
    TransitionScript,
)


# ---------------------------------------------------------------------------
# Music Selector Tests
# ---------------------------------------------------------------------------


class TestMusicSelector:
    """Tests for music_selector.select_next_track."""

    @pytest.fixture
    def mock_pool(self):
        pool = MagicMock()
        conn = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__.return_value = conn
        cm.__aexit__.return_value = False
        pool.acquire.return_value = cm
        return pool, conn

    @pytest.fixture
    def sample_track_rows(self):
        return [
            {
                "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
                "title": "Chill Vibes",
                "artist": "DJ Smooth",
                "file_path": "/music/library/chill_vibes.mp3",
                "duration_seconds": 240,
                "genre": "lounge",
                "mood": "chill",
                "similarity": 0.92,
            },
            {
                "id": uuid.UUID("22222222-2222-2222-2222-222222222222"),
                "title": "Night Jazz",
                "artist": "Jazz Cat",
                "file_path": "/music/library/night_jazz.mp3",
                "duration_seconds": 300,
                "genre": "jazz",
                "mood": "relaxed",
                "similarity": 0.85,
            },
        ]

    async def test_select_with_embedding_similarity(self, mock_pool, sample_track_rows):
        """Music selector queries pgvector with embedding similarity and excludes recently played tracks."""
        from app.features.content.services.music_selector import select_next_track

        pool, conn = mock_pool
        conn.fetch.return_value = sample_track_rows

        mock_embedding = AsyncMock()
        mock_embedding.embed.return_value = [[0.1, 0.2, 0.3]]

        result = await select_next_track(
            pool,
            block_description="chill evening jazz",
            previous_track_ids=["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"],
            embedding_adapter=mock_embedding,
        )

        assert result is not None
        assert isinstance(result, MusicSelection)
        assert result.track_id == "11111111-1111-1111-1111-111111111111"
        assert result.title == "Chill Vibes"
        assert result.artist == "DJ Smooth"
        mock_embedding.embed.assert_called_once()

    async def test_fallback_to_random_when_no_embeddings(self, mock_pool, sample_track_rows):
        """Falls back to random track selection when no embedding adapter."""
        from app.features.content.services.music_selector import select_next_track

        pool, conn = mock_pool
        conn.fetch.return_value = sample_track_rows

        result = await select_next_track(
            pool,
            block_description="morning show",
            previous_track_ids=[],
            embedding_adapter=None,
        )

        assert result is not None
        assert isinstance(result, MusicSelection)
        # Should use the fallback query (no embedding)
        conn.fetch.assert_called_once()

    async def test_respects_rolling_window_filter(self, mock_pool, sample_track_rows):
        """Filters out recently played track IDs."""
        from app.features.content.services.music_selector import select_next_track

        pool, conn = mock_pool
        conn.fetch.return_value = sample_track_rows

        previous_ids = [
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        ]

        result = await select_next_track(
            pool,
            block_description="rock hour",
            previous_track_ids=previous_ids,
            embedding_adapter=None,
        )

        assert result is not None
        # Verify the query was called with the previous IDs for exclusion
        call_args = conn.fetch.call_args
        assert previous_ids == call_args[0][1] or previous_ids == call_args.args[1]

    async def test_returns_none_when_no_tracks(self, mock_pool):
        """Returns None when no tracks are available."""
        from app.features.content.services.music_selector import select_next_track

        pool, conn = mock_pool
        conn.fetch.return_value = []

        result = await select_next_track(
            pool,
            block_description="empty library",
            previous_track_ids=[],
        )

        assert result is None

    async def test_llm_curation_selects_best_track(self, mock_pool, sample_track_rows):
        """LLM picks the best track from candidates when available."""
        from app.features.content.services.music_selector import select_next_track

        pool, conn = mock_pool
        conn.fetch.return_value = sample_track_rows

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = MagicMock(
            content='{"track_id": "22222222-2222-2222-2222-222222222222", "reason": "Perfect jazz mood"}'
        )

        result = await select_next_track(
            pool,
            block_description="late night jazz",
            previous_track_ids=[],
            embedding_adapter=None,
            llm=mock_llm,
        )

        assert result is not None
        assert result.track_id == "22222222-2222-2222-2222-222222222222"
        assert "jazz" in result.reason.lower() or result.reason == "Perfect jazz mood"


# ---------------------------------------------------------------------------
# Transition Generator Tests
# ---------------------------------------------------------------------------


class TestTransitionGenerator:
    """Tests for transition_generator.generate_transition."""

    @pytest.fixture
    def mock_llm(self):
        llm = AsyncMock()
        llm.generate.return_value = MagicMock(
            content="Hey listeners, next up we have a beautiful track for you..."
        )
        return llm

    @pytest.fixture
    def mock_tool_registry(self):
        registry = MagicMock()
        registry.get_all_schemas.return_value = []
        return registry

    @pytest.fixture
    def sample_host(self):
        return {
            "id": "host-1",
            "name": "DJ Chill",
            "language": "en",
            "description": {"self_description": "A laid-back DJ who loves jazz"},
            "template_id": "chill_dj",
        }

    @pytest.fixture
    def sample_template_data(self):
        return {
            "prompt_templates": {
                "core_identity_template": "You are {name}, {core_identity}. Speak in {language}.",
                "output_format_voice": "No emojis. Use natural speech.",
                "greeting_prompt": "Introduce yourself to the listeners.",
                "show_intro_template": "Open the show with energy.",
                "track_intro_template": "Announce the next track.",
            }
        }

    @pytest.fixture
    def sample_context(self):
        return BlockContext(
            time_of_day="evening",
            block_description="Smooth jazz evening session",
            previous_tracks=["Track A by Artist A"],
            is_block_start=False,
            host_language="en",
        )

    async def test_generate_transition_calls_ai_gateway(
        self, mock_llm, mock_tool_registry, sample_host, sample_template_data, sample_context
    ):
        """Calls AIGateway with assembled system prompt and segment prompt."""
        from app.features.content.services.transition_generator import generate_transition

        with patch("app.features.content.services.transition_generator.run_ai_gateway") as mock_gateway:
            mock_gateway.return_value = MagicMock(
                content="Here comes a great track..."
            )

            result = await generate_transition(
                llm=mock_llm,
                tool_registry=mock_tool_registry,
                host=sample_host,
                template_data=sample_template_data,
                context=sample_context,
                segment_type=ContentSegmentType.TRACK_INTRO,
            )

            assert isinstance(result, TransitionScript)
            assert result.text == "Here comes a great track..."
            assert result.segment_type == ContentSegmentType.TRACK_INTRO
            mock_gateway.assert_called_once()

    async def test_max_tokens_by_segment_type(
        self, mock_llm, mock_tool_registry, sample_host, sample_template_data, sample_context
    ):
        """Sets max_tokens based on segment type for character budget enforcement."""
        from app.features.content.services.transition_generator import generate_transition

        expected_tokens = {
            ContentSegmentType.TRACK_INTRO: 150,
            ContentSegmentType.SHOW_INTRO: 250,
            ContentSegmentType.GREETING: 200,
            ContentSegmentType.TRANSITION: 200,
            ContentSegmentType.BUMPER: 80,
        }

        for seg_type, expected_max in expected_tokens.items():
            with patch("app.features.content.services.transition_generator.run_ai_gateway") as mock_gateway:
                mock_gateway.return_value = MagicMock(content="Some text")

                await generate_transition(
                    llm=mock_llm,
                    tool_registry=mock_tool_registry,
                    host=sample_host,
                    template_data=sample_template_data,
                    context=sample_context,
                    segment_type=seg_type,
                )

                call_kwargs = mock_gateway.call_args
                assert call_kwargs.kwargs.get("max_tokens") == expected_max, (
                    f"Expected max_tokens={expected_max} for {seg_type}, "
                    f"got {call_kwargs.kwargs.get('max_tokens')}"
                )

    async def test_fallback_script_on_error(
        self, mock_llm, mock_tool_registry, sample_host, sample_template_data, sample_context
    ):
        """Returns a fallback script when AIGateway fails."""
        from app.features.content.services.transition_generator import generate_transition

        with patch("app.features.content.services.transition_generator.run_ai_gateway") as mock_gateway:
            mock_gateway.side_effect = Exception("LLM API error")

            result = await generate_transition(
                llm=mock_llm,
                tool_registry=mock_tool_registry,
                host=sample_host,
                template_data=sample_template_data,
                context=sample_context,
                segment_type=ContentSegmentType.TRACK_INTRO,
            )

            assert isinstance(result, TransitionScript)
            assert result.segment_type == ContentSegmentType.TRACK_INTRO
            # Fallback text should be something generic
            assert len(result.text) > 0


# ---------------------------------------------------------------------------
# TTS Pipeline Tests
# ---------------------------------------------------------------------------


class TestTTSPipeline:
    """Tests for tts_pipeline.synthesize_and_push."""

    @pytest.fixture
    def mock_tts_adapter(self):
        adapter = AsyncMock()
        adapter.is_configured = True
        adapter.synthesize.return_value = b"\xff\xfb\x90\x00" * 100  # fake MP3 bytes
        # prepare_text is sync — pass through text unchanged
        adapter.prepare_text = MagicMock(side_effect=lambda text: text)
        return adapter

    async def test_synthesize_and_push_full_flow(self, mock_tts_adapter, tmp_path):
        """Synthesizes text via ElevenLabs, writes file, pushes to Liquidsoap."""
        from app.features.content.services.tts_pipeline import synthesize_and_push

        segment_id = "seg-001"

        with patch("app.features.content.services.tts_pipeline.GENERATED_DIR", tmp_path / "generated"), \
             patch("app.features.content.services.tts_pipeline.push_track") as mock_push:
            mock_push.return_value = {"status": "ok"}

            result = await synthesize_and_push(
                tts_adapter=mock_tts_adapter,
                text="Hello listeners!",
                voice_id="voice-abc",
                segment_id=segment_id,
            )

            assert result is not None
            assert segment_id in result
            mock_tts_adapter.synthesize.assert_called_once_with("Hello listeners!", "voice-abc")
            mock_push.assert_called_once()

    async def test_returns_none_when_not_configured(self):
        """Returns None gracefully when TTS adapter is not configured."""
        from app.features.content.services.tts_pipeline import synthesize_and_push

        adapter = AsyncMock()
        adapter.is_configured = False

        result = await synthesize_and_push(
            tts_adapter=adapter,
            text="Test",
            voice_id="voice-123",
            segment_id="seg-002",
        )

        assert result is None

    async def test_creates_generated_directory(self, mock_tts_adapter, tmp_path):
        """Creates the generated directory if it doesn't exist."""
        from app.features.content.services.tts_pipeline import synthesize_and_push

        gen_dir = tmp_path / "new_generated"
        assert not gen_dir.exists()

        with patch("app.features.content.services.tts_pipeline.GENERATED_DIR", gen_dir), \
             patch("app.features.content.services.tts_pipeline.push_track") as mock_push:
            mock_push.return_value = {"status": "ok"}

            await synthesize_and_push(
                tts_adapter=mock_tts_adapter,
                text="Create dir test",
                voice_id="voice-xyz",
                segment_id="seg-003",
            )

            assert gen_dir.exists()

    async def test_returns_none_on_empty_bytes(self):
        """Returns None when TTS returns empty bytes."""
        from app.features.content.services.tts_pipeline import synthesize_and_push

        adapter = AsyncMock()
        adapter.is_configured = True
        adapter.synthesize.return_value = b""

        result = await synthesize_and_push(
            tts_adapter=adapter,
            text="Empty test",
            voice_id="voice-empty",
            segment_id="seg-004",
        )

        assert result is None

    async def test_push_music_track_success(self):
        """push_music_track returns True on success."""
        from app.features.content.services.tts_pipeline import push_music_track

        with patch("app.features.content.services.tts_pipeline.push_track") as mock_push:
            mock_push.return_value = {"status": "ok"}

            result = await push_music_track("/music/library/track.mp3")

            assert result is True
            mock_push.assert_called_once_with("/music/library/track.mp3")

    async def test_push_music_track_failure(self):
        """push_music_track returns False on failure."""
        from app.features.content.services.tts_pipeline import push_music_track

        with patch("app.features.content.services.tts_pipeline.push_track") as mock_push:
            mock_push.side_effect = Exception("Connection refused")

            result = await push_music_track("/music/library/track.mp3")

            assert result is False


# ---------------------------------------------------------------------------
# Bumper Generator Tests
# ---------------------------------------------------------------------------


class TestBumperGenerator:
    """Tests for bumper_generator.generate_bumpers."""

    @pytest.fixture
    def mock_llm(self):
        llm = AsyncMock()
        llm.generate.return_value = MagicMock(
            content="You're listening to Tramontane Radio\nTramontane Radio, your vibe\nStay tuned to Tramontane"
        )
        return llm

    @pytest.fixture
    def mock_tts(self):
        adapter = AsyncMock()
        adapter.is_configured = True
        adapter.synthesize.return_value = b"\xff\xfb\x90\x00" * 50
        return adapter

    async def test_generates_bumper_phrases_via_llm(self, mock_llm, mock_tts, tmp_path):
        """Generates 2-3 bumper phrases via LLM and synthesizes each via TTS."""
        from app.features.content.services.bumper_generator import generate_bumpers

        with patch("app.features.content.services.bumper_generator.BUMPERS_DIR", tmp_path / "bumpers"):
            result = await generate_bumpers(
                llm=mock_llm,
                tts_adapter=mock_tts,
                voice_id="voice-bumper",
                station_name="Tramontane Radio",
                count=3,
            )

            assert len(result) == 3
            mock_llm.generate.assert_called_once()
            assert mock_tts.synthesize.call_count == 3

    async def test_writes_mp3_files_to_bumpers_dir(self, mock_llm, mock_tts, tmp_path):
        """Writes MP3 files to /music/bumpers/ directory."""
        from app.features.content.services.bumper_generator import generate_bumpers

        bumpers_dir = tmp_path / "bumpers"

        with patch("app.features.content.services.bumper_generator.BUMPERS_DIR", bumpers_dir):
            result = await generate_bumpers(
                llm=mock_llm,
                tts_adapter=mock_tts,
                voice_id="voice-bumper",
                count=3,
            )

            assert bumpers_dir.exists()
            mp3_files = list(bumpers_dir.glob("*.mp3"))
            assert len(mp3_files) == 3
            for path in result:
                assert Path(path).exists()

    async def test_skips_generation_if_bumpers_exist(self, mock_llm, mock_tts, tmp_path):
        """Skips generation if bumpers already exist on disk."""
        from app.features.content.services.bumper_generator import generate_bumpers

        bumpers_dir = tmp_path / "bumpers"
        bumpers_dir.mkdir(parents=True)
        # Create 3 existing bumper files
        for i in range(3):
            (bumpers_dir / f"bumper_{i}.mp3").write_bytes(b"\xff\xfb\x90\x00")

        with patch("app.features.content.services.bumper_generator.BUMPERS_DIR", bumpers_dir):
            result = await generate_bumpers(
                llm=mock_llm,
                tts_adapter=mock_tts,
                voice_id="voice-bumper",
                count=3,
            )

            # Should return existing paths without calling LLM or TTS
            assert len(result) == 3
            mock_llm.generate.assert_not_called()
            mock_tts.synthesize.assert_not_called()
