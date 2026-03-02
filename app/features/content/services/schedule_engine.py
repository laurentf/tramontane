"""Schedule engine v2 -- buffer-aware queue management with block boundary handoffs.

The schedule_tick runs every 30 seconds. Instead of blind timer-based pushing,
it tracks an estimated audio budget and only pushes when the buffer runs low.
Block boundaries trigger closing/opening handoff segments with host names.

Dead-hour awareness: no LLM/TTS calls when no active block is scheduled.
"""

import time
import uuid
from datetime import datetime
from typing import Any

import structlog

from app.features.content.repositories.play_history import PlayHistoryRepository
from app.features.content.schemas.content import (
    BlockContext,
    ContentSegmentType,
)
from app.features.content.services.music_selector import select_next_track
from app.features.content.services.transition_generator import generate_transition
from app.features.content.services.tts_pipeline import push_music_track, synthesize_and_push
from app.features.hosts.repositories.host_repository import HostRepository
from app.features.hosts.templates import get_template
from app.features.schedule.repositories.schedule_repository import ScheduleRepository

logger = structlog.get_logger(__name__)

# Buffer constants
BUFFER_LOW_SEC = 90.0  # Push new content when budget drops below this
CLOSING_WINDOW_SEC = 60.0  # Start closing when < 60s remain in block
TTS_ESTIMATE_SEC = 8.0  # Rough duration of a TTS voice segment


def _time_diff_seconds(from_time, to_time) -> float:
    """Seconds between two datetime.time values, handling midnight wrap."""
    from_sec = from_time.hour * 3600 + from_time.minute * 60 + from_time.second
    to_sec = to_time.hour * 3600 + to_time.minute * 60 + to_time.second
    diff = to_sec - from_sec
    if diff < 0:
        diff += 86400  # wrap around midnight
    return float(diff)


async def arq_enqueue(ctx: dict[str, Any], task_name: str, *args: Any, **kwargs: Any) -> None:
    """Enqueue an ARQ job. Wraps ctx-based enqueue for testability."""
    try:
        redis = ctx.get("redis")
        if redis:
            await redis.enqueue_job(task_name, *args, **kwargs)
        else:
            logger.info(
                "schedule_engine.enqueue_fallback",
                task=task_name,
                msg="No redis in ctx, job enqueued as direct call",
            )
    except Exception:
        logger.exception("schedule_engine.enqueue_error", task=task_name)


async def _sync_state_to_redis(ctx: dict[str, Any]) -> None:
    """Persist schedule engine state to Redis for cross-tick continuity.

    ARQ cron ctx dict resets every tick, so all persistent state lives in Redis.
    """
    redis = ctx.get("redis")
    if not redis:
        return
    try:
        await redis.set("sched:last_tick_ts", str(ctx.get("last_tick_ts", 0)), ex=300)
        await redis.set("sched:budget", str(ctx.get("queue_budget_sec", 0)), ex=300)
        block_id = ctx.get("current_block_id")
        if block_id:
            await redis.set("sched:block_id", str(block_id), ex=300)
        else:
            await redis.delete("sched:block_id")
        if ctx.get("closing_pushed"):
            await redis.set("sched:closing_pushed", "1", ex=7200)
        else:
            await redis.delete("sched:closing_pushed")
    except Exception:
        logger.warning("schedule_engine.state_sync_error")


async def schedule_tick(ctx: dict[str, Any]) -> None:
    """ARQ cron job -- runs every 30 seconds.

    Buffer-aware: tracks estimated audio queued and only pushes when low.
    Block-aware: handles opening/closing handoffs with adjacent host names.
    """
    pool = ctx["pool"]
    repo = ScheduleRepository(pool)
    now = time.time()
    now_dt = datetime.now()
    now_time = now_dt.time()

    # 1. Load persistent state from Redis (ARQ cron ctx resets every tick)
    redis = ctx.get("redis")
    if redis:
        raw_ts = await redis.get("sched:last_tick_ts")
        raw_b = await redis.get("sched:budget")
        raw_cp = await redis.get("sched:closing_pushed")
        raw_bid = await redis.get("sched:block_id")
        if raw_ts:
            ctx.setdefault("last_tick_ts", float(raw_ts))
        if raw_b:
            ctx.setdefault("queue_budget_sec", float(raw_b))
        if raw_cp:
            ctx.setdefault("closing_pushed", True)
        if raw_bid:
            bid = raw_bid.decode() if isinstance(raw_bid, bytes) else str(raw_bid)
            ctx.setdefault("current_block_id", bid)

    # Drain budget by elapsed time
    elapsed = now - ctx.get("last_tick_ts", now)
    ctx["last_tick_ts"] = now
    budget = max(0.0, ctx.get("queue_budget_sec", 0.0) - elapsed)
    ctx["queue_budget_sec"] = budget

    # 2. Find active block
    active_block = await repo.get_active_block()

    if active_block is None:
        # Dead-hour awareness (SCHED-04): reset state, do nothing
        logger.debug("schedule_engine.no_active_block")
        ctx["current_block_id"] = None
        ctx["closing_pushed"] = False
        ctx["queue_budget_sec"] = 0.0

        # Check for upcoming blocks to pre-generate (SCHED-03)
        upcoming = await repo.get_upcoming_blocks(within_seconds=60)
        if upcoming:
            for block in upcoming:
                bid = str(block["id"])
                dispatched_key = f"pre_{bid}"
                if not ctx.get(dispatched_key):
                    ctx[dispatched_key] = True
                    logger.info(
                        "schedule_engine.pre_generate",
                        block_id=bid,
                        block_name=block.get("name"),
                    )
                    await arq_enqueue(
                        ctx,
                        "generate_content_segment",
                        bid,
                        is_opening=True,
                    )
        await _sync_state_to_redis(ctx)
        return

    block_id = str(active_block["id"])
    block_end = active_block["end_time"]  # datetime.time object
    block_start = active_block["start_time"]

    # 3. Block transition / cold-start detection
    prev_block_id = ctx.get("current_block_id")
    ctx["current_block_id"] = block_id  # Set immediately to prevent re-entry

    if prev_block_id and prev_block_id != block_id:
        # Host handoff: block changed while running
        logger.info(
            "schedule_engine.block_transition",
            from_block=prev_block_id,
            to_block=block_id,
        )
        if redis:
            await redis.set(f"track_count:{block_id}", 0)

        prev_block = await repo.get_previous_block(str(block_start))
        previous_host_name = prev_block.get("host_name") if prev_block else None

        await _push_opening(ctx, pool, active_block, previous_host_name=previous_host_name)
        ctx["queue_budget_sec"] += TTS_ESTIMATE_SEC
        ctx["closing_pushed"] = False

    elif prev_block_id is None:
        # Cold start: worker just booted into an active block
        # Use Redis to prevent duplicate cold starts (ctx doesn't survive between ticks)
        if redis:
            already = await redis.get("cold_start_done")
            if already:
                logger.debug("schedule_engine.cold_start_skip", block_id=block_id)
                # Fall through to normal buffer-based dispatch
                pass
            else:
                await redis.set("cold_start_done", block_id, ex=3600)
                await _do_cold_start(ctx, pool, active_block, block_id, redis)
                await _sync_state_to_redis(ctx)
                return  # Opening + first track done, don't fall through
        else:
            await _do_cold_start(ctx, pool, active_block, block_id, None)
            await _sync_state_to_redis(ctx)
            return

    # Refresh local budget after potential transition modifications
    budget = ctx.get("queue_budget_sec", 0.0)

    # 4. How much time remains in this block?
    block_remaining_sec = _time_diff_seconds(now_time, block_end)

    # 5. Closing window?
    if (
        block_remaining_sec < CLOSING_WINDOW_SEC
        and not ctx.get("closing_pushed")
        and budget < block_remaining_sec
    ):
        logger.info(
            "schedule_engine.closing_window",
            block_id=block_id,
            block_remaining_sec=round(block_remaining_sec, 1),
            budget=round(budget, 1),
        )
        # Fetch next block for handoff name
        next_block = await repo.get_next_block(str(block_end))
        next_host_name = next_block.get("host_name") if next_block else None

        await _push_closing(ctx, pool, active_block, next_host_name=next_host_name)
        # Push one last track after closing voice
        await _push_track_with_voice(ctx, pool, active_block, is_last=True)
        ctx["closing_pushed"] = True
        await _sync_state_to_redis(ctx)
        return

    # 6. Already pushed closing -- stop feeding this block
    if ctx.get("closing_pushed"):
        logger.debug("schedule_engine.closing_draining", block_id=block_id)
        await _sync_state_to_redis(ctx)
        return

    # 7. Buffer still healthy -- skip
    if budget > BUFFER_LOW_SEC:
        logger.debug(
            "schedule_engine.buffer_healthy",
            block_id=block_id,
            budget=round(budget, 1),
        )
        await _sync_state_to_redis(ctx)
        return

    # 8. Push next track (with voice intro per pacing)
    logger.info(
        "schedule_engine.dispatch",
        block_id=block_id,
        block_name=active_block.get("name"),
        host_name=active_block.get("host_name"),
        budget=round(budget, 1),
    )
    await _push_track_with_voice(ctx, pool, active_block)
    await _sync_state_to_redis(ctx)


async def _push_opening(
    ctx: dict[str, Any],
    pool,
    block: dict,
    *,
    previous_host_name: str | None = None,
    track_info: dict | None = None,
) -> None:
    """Push a BLOCK_OPENING voice segment for a new host."""
    host, template_data, context = await _load_segment_context(pool, block, is_opening=True)
    if not host:
        return

    llm = _create_llm()
    tts = _create_tts()
    voice_id = host.get("voice_id", "")

    # Pre-fetch weather + news so the opening always has both
    tool_context_parts = await _prefetch_opening_tools()

    from app.providers.tools.registry import ToolRegistry
    empty_registry = ToolRegistry()

    script = await generate_transition(
        llm=llm,
        tool_registry=empty_registry,
        host=host,
        template_data=template_data,
        context=context,
        segment_type=ContentSegmentType.BLOCK_OPENING,
        previous_host_name=previous_host_name,
        track_info=track_info,
        skill_prompts=tool_context_parts or None,
    )
    logger.info("schedule_engine.script_generated", segment="opening", text=script.text[:120])

    if tts and voice_id:
        seg_id = f"opening-{uuid.uuid4()}"
        await synthesize_and_push(
            tts_adapter=tts,
            text=script.text,
            voice_id=voice_id,
            segment_id=seg_id,
        )
    else:
        logger.info("schedule_engine.tts_skip", reason="tts disabled or no voice_id")


async def _push_closing(
    ctx: dict[str, Any],
    pool,
    block: dict,
    *,
    next_host_name: str | None = None,
) -> None:
    """Push a BLOCK_CLOSING voice segment for an outgoing host."""
    host, template_data, context = await _load_segment_context(pool, block)
    if not host:
        return

    llm = _create_llm()
    tts = _create_tts()
    voice_id = host.get("voice_id", "")

    tool_registry = _create_tool_registry()

    script = await generate_transition(
        llm=llm,
        tool_registry=tool_registry,
        host=host,
        template_data=template_data,
        context=context,
        segment_type=ContentSegmentType.BLOCK_CLOSING,
        next_host_name=next_host_name,
    )
    logger.info("schedule_engine.script_generated", segment="closing", text=script.text[:120])

    if tts and voice_id:
        seg_id = f"closing-{uuid.uuid4()}"
        await synthesize_and_push(
            tts_adapter=tts,
            text=script.text,
            voice_id=voice_id,
            segment_id=seg_id,
        )
    else:
        logger.info("schedule_engine.tts_skip", reason="tts disabled or no voice_id")


async def _push_track_with_voice(
    ctx: dict[str, Any],
    pool,
    block: dict,
    *,
    is_last: bool = False,
) -> None:
    """Select and push a track, optionally with a voice transition.

    Updates the budget in ctx based on track duration.
    """
    block_id = str(block["id"])
    host, template_data, context = await _load_segment_context(pool, block)
    if not host:
        return

    host_id = str(block.get("host_id", ""))
    play_history_repo = PlayHistoryRepository(pool)
    recent_ids = await play_history_repo.get_recent_track_ids(host_id=host_id, limit=20)

    llm = _create_llm()
    tts = _create_tts()
    embedding = _create_embedding()
    voice_id = host.get("voice_id", "")

    tool_registry = _create_tool_registry()

    # Select next track
    selection = await select_next_track(
        pool,
        block_description=context.block_description,
        previous_track_ids=recent_ids,
        embedding_adapter=embedding,
        llm=llm,
    )

    if not selection:
        logger.warning("schedule_engine.no_track_selected", block_id=block_id)
        return

    logger.info(
        "schedule_engine.track_selected",
        track=selection.title,
        artist=selection.artist,
        reason=selection.reason,
    )

    # Fetch previous track info for transitions
    from app.features.ingest.repositories.track_repository import TrackRepository

    previous_track_info = None
    if recent_ids:
        track_repo = TrackRepository(pool)
        prev = await track_repo.get_by_id(str(recent_ids[0]))
        if prev:
            previous_track_info = {"title": prev["title"], "artist": prev["artist"]}

    # Check pacing ratio for transitions
    redis = ctx.get("redis")
    track_count = 0
    if redis:
        raw = await redis.get(f"track_count:{block_id}")
        track_count = int(raw) if raw else 0

    # Always transition between tracks — host reacts to previous + introduces next
    logger.info("schedule_engine.transition_generating", segment_type="track_intro")
    script = await generate_transition(
        llm=llm,
        tool_registry=tool_registry,
        host=host,
        template_data=template_data,
        context=context,
        segment_type=ContentSegmentType.TRACK_INTRO,
        track_info={"title": selection.title, "artist": selection.artist},
        previous_track=previous_track_info,
    )
    logger.info(
        "schedule_engine.script_generated",
        segment="transition",
        text=script.text[:120],
    )
    if tts and voice_id:
        await synthesize_and_push(
            tts_adapter=tts,
            text=script.text,
            voice_id=voice_id,
            segment_id=str(uuid.uuid4()),
        )
        ctx["queue_budget_sec"] = ctx.get("queue_budget_sec", 0.0) + TTS_ESTIMATE_SEC
    else:
        logger.info("schedule_engine.tts_skip", reason="tts disabled or no voice_id")

    # Push the music track
    logger.info("schedule_engine.pushing_track", file_path=selection.file_path)
    await push_music_track(selection.file_path)

    # Update budget with track duration
    track_duration = selection.duration_seconds or 210.0  # fallback ~3.5 min
    ctx["queue_budget_sec"] = ctx.get("queue_budget_sec", 0.0) + track_duration

    # Record play in history
    await play_history_repo.record_play(
        track_id=selection.track_id,
        block_id=block_id,
        host_id=host_id,
    )

    # Increment track counter in Redis
    if redis:
        await redis.incr(f"track_count:{block_id}")

    logger.info(
        "schedule_engine.segment_complete",
        block_id=block_id,
        track=selection.title,
        artist=selection.artist,
        transition=True,
        track_count=track_count + 1,
        budget=round(ctx.get("queue_budget_sec", 0.0), 1),
    )


async def _load_segment_context(
    pool,
    block: dict,
    *,
    is_opening: bool = False,
) -> tuple[dict | None, dict, BlockContext]:
    """Load host, template, and block context for segment generation.

    Returns (host, template_data, context). Host is None if not found.
    """
    block_id = str(block["id"])
    host_id = str(block.get("host_id", ""))
    host_repo = HostRepository(pool)
    host = await host_repo.get_by_id_unscoped(host_id)
    if not host:
        logger.warning("schedule_engine.no_host", block_id=block_id, host_id=host_id)
        return None, {}, BlockContext(time_of_day="", block_description="")

    template_id = host.get("template_id") or block.get("host_template_id")
    template = get_template(template_id) if template_id else None
    template_data = template.model_dump() if template else {"prompt_templates": {}}

    play_history_repo = PlayHistoryRepository(pool)
    recent_ids = await play_history_repo.get_recent_track_ids(host_id=host_id, limit=20)
    previous_track_descs = [str(tid) for tid in recent_ids[:5]]

    now = datetime.now()
    time_of_day = _get_time_of_day(now.hour)

    from app.core.config import get_settings
    settings = get_settings()

    context = BlockContext(
        time_of_day=time_of_day,
        block_description=block.get("description", "") or block.get("name", ""),
        previous_tracks=previous_track_descs,
        is_block_start=is_opening,
        host_language=host.get("language", "fr"),
        current_datetime=_format_datetime(now, host.get("language", "fr")),
        station_location=settings.station_location,
    )

    return host, template_data, context


async def generate_content_segment(
    ctx: dict[str, Any],
    block_id: str,
    *,
    is_opening: bool = False,
    is_closing: bool = False,
) -> None:
    """Generate and push a content segment for a schedule block.

    Kept as an ARQ-registered task for manual triggers and pre-generation.
    Normal dispatch now goes through schedule_tick -> _push_track_with_voice inline.
    """
    pool = ctx["pool"]
    schedule_repo = ScheduleRepository(pool)
    block = await schedule_repo.get_by_id_unscoped(block_id)
    if not block:
        logger.error("schedule_engine.block_not_found", block_id=block_id)
        return

    if is_closing:
        await _push_closing(ctx, pool, block)
        return

    if is_opening:
        await _push_opening(ctx, pool, block)
        return

    # Normal segment: push track with voice
    await _push_track_with_voice(ctx, pool, block)


async def _do_cold_start(
    ctx: dict[str, Any], pool, block: dict, block_id: str, redis
) -> None:
    """Execute cold-start sequence: flush queue, push opening + first track."""
    from app.features.radio.services.liquidsoap_client import flush_queue

    logger.info(
        "schedule_engine.cold_start",
        block_id=block_id,
        host_name=block.get("host_name"),
    )

    # Flush stale tracks from previous worker runs
    await flush_queue()

    first_track_info = await _select_first_track(pool, block)
    await _push_opening(ctx, pool, block, track_info=first_track_info)
    ctx["queue_budget_sec"] = ctx.get("queue_budget_sec", 0.0) + TTS_ESTIMATE_SEC
    ctx["closing_pushed"] = False

    # Push the pre-selected track right after the opening voice
    if first_track_info and first_track_info.get("_selection"):
        selection = first_track_info["_selection"]
        await push_music_track(selection.file_path)
        track_duration = selection.duration_seconds or 210.0
        ctx["queue_budget_sec"] += track_duration

        host_id = str(block.get("host_id", ""))
        play_history_repo = PlayHistoryRepository(pool)
        await play_history_repo.record_play(
            track_id=selection.track_id,
            block_id=block_id,
            host_id=host_id,
        )
        if redis:
            await redis.set(f"track_count:{block_id}", 1)

        logger.info(
            "schedule_engine.cold_start_track",
            track=selection.title,
            artist=selection.artist,
            budget=round(ctx.get("queue_budget_sec", 0.0), 1),
        )


async def _select_first_track(pool, block: dict) -> dict | None:
    """Pre-select the first track for a cold-start opening announcement."""
    host_id = str(block.get("host_id", ""))
    block_desc = block.get("description", "") or block.get("name", "")

    play_history_repo = PlayHistoryRepository(pool)
    recent_ids = await play_history_repo.get_recent_track_ids(host_id=host_id, limit=20)

    embedding = _create_embedding()
    llm = _create_llm()

    selection = await select_next_track(
        pool,
        block_description=block_desc,
        previous_track_ids=recent_ids,
        embedding_adapter=embedding,
        llm=llm,
    )
    if not selection:
        return None

    return {
        "title": selection.title,
        "artist": selection.artist,
        "_selection": selection,  # carry full object for push
    }


def _format_datetime(dt: datetime, language: str = "fr") -> str:
    """Format datetime in a human-friendly way for the given language.

    Uses manual day/month names to avoid locale dependency in Docker containers.
    """
    _DAYS = {
        "fr": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
        "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "es": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
    }
    _MONTHS = {
        "fr": ["janvier", "février", "mars", "avril", "mai", "juin",
               "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
        "en": ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"],
        "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio",
               "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
    }
    days = _DAYS.get(language, _DAYS["fr"])
    months = _MONTHS.get(language, _MONTHS["fr"])
    day_name = days[dt.weekday()]
    month_name = months[dt.month - 1]
    return f"{day_name} {dt.day} {month_name} {dt.year}, {dt.hour}h{dt.minute:02d}"


def _get_time_of_day(hour: int) -> str:
    """Map hour to a human-friendly time-of-day description."""
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "night"


def _create_llm():
    """Lazily create an LLM adapter from settings."""
    try:
        from app.core.config import get_settings
        from app.providers.llm.mistral.adapter import MistralLLMAdapter

        settings = get_settings()
        if settings.mistral_api_key:
            return MistralLLMAdapter(api_key=settings.mistral_api_key.get_secret_value())
    except Exception:
        logger.debug("schedule_engine.no_llm", msg="LLM adapter not available")
    return None


def _create_tts():
    """Lazily create a TTS adapter from settings."""
    try:
        from app.core.config import get_settings
        from app.providers.speech.tts.elevenlabs.adapter import ElevenLabsTTSAdapter

        settings = get_settings()
        if settings.elevenlabs_api_key:
            return ElevenLabsTTSAdapter(
                api_key=settings.elevenlabs_api_key.get_secret_value(),
                default_model=settings.tts_model,
            )
    except Exception:
        logger.debug("schedule_engine.no_tts", msg="TTS adapter not available")
    return None


def _create_embedding():
    """Lazily create an embedding adapter from settings."""
    try:
        from app.core.config import get_settings
        from app.providers.embedding.mistral.adapter import MistralEmbeddingAdapter

        settings = get_settings()
        if settings.mistral_api_key:
            return MistralEmbeddingAdapter(api_key=settings.mistral_api_key.get_secret_value())
    except Exception:
        logger.debug("schedule_engine.no_embedding", msg="Embedding adapter not available")
    return None


async def _prefetch_opening_tools() -> list[str]:
    """Pre-fetch weather and news for block openings."""
    tool_registry = _create_tool_registry()
    if not tool_registry:
        return []

    from app.core.config import get_settings
    settings = get_settings()
    location = settings.station_location or "Montpellier, France"
    parts: list[str] = []

    try:
        weather = await tool_registry.execute("weather", {"location": location})
        if weather.success:
            parts.append(f"CURRENT WEATHER: {weather.result}")
            logger.info("schedule_engine.prefetch_weather", result=weather.result[:80])
    except Exception:
        logger.warning("schedule_engine.prefetch_weather_failed")

    try:
        news = await tool_registry.execute(
            "web_search", {"query": "top news headlines today world"}
        )
        if news.success:
            # Strip tool handler's default instructions — the template provides its own
            raw = news.result.split("\n\nIMPORTANT:")[0].strip()
            parts.append(f"LATEST NEWS:\n{raw}")
            logger.info("schedule_engine.prefetch_news", result_len=len(raw))
    except Exception:
        logger.warning("schedule_engine.prefetch_news_failed")

    return parts


def _create_tool_registry():
    """Create a ToolRegistry with weather + search tools if API keys are configured."""
    from app.core.config import get_settings
    from app.providers.tools.registry import ToolRegistry

    tool_registry = ToolRegistry()
    settings = get_settings()

    if settings.openweather_api_key:
        from app.providers.tools.handlers.weather import WeatherToolHandler
        from app.providers.weather.openweathermap.adapter import OpenWeatherMapAdapter

        weather_adapter = OpenWeatherMapAdapter(
            api_key=settings.openweather_api_key.get_secret_value(),
        )
        tool_registry.register(WeatherToolHandler(weather_adapter))
        logger.info("schedule_engine.tool_registered", tool="weather")

    if settings.tavily_api_key:
        from app.providers.search.tavily.adapter import TavilySearchAdapter
        from app.providers.tools.handlers.search import SearchToolHandler

        search_adapter = TavilySearchAdapter(
            api_key=settings.tavily_api_key.get_secret_value(),
        )
        tool_registry.register(SearchToolHandler(search_adapter))
        logger.info("schedule_engine.tool_registered", tool="web_search")

    return tool_registry
