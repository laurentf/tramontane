# Tramontane Radio - Liquidsoap 2.4.2
# Pipeline: queue -> fallback -> normalize -> Icecast output
# Harbor HTTP on port 8080 for track push

# Enable telnet server for queue control
settings.server.telnet := true
settings.server.telnet.port := 1234

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

queue = request.queue(id="queue")

# Pre-recorded station bumpers for idle hours (generated once via LLM+TTS).
# Played during dead hours when no active block is scheduled, giving the
# station a radio feel without ongoing token cost.
bumpers = playlist(id="bumpers", mode="randomize", reload_mode="watch", "/music/bumpers/")

fallback_playlist = playlist(id="fallback", mode="random", "/music/library/")

# Fallback chain: queue -> bumpers -> library -> silence
# /music/generated/ paths start with /music/, so push_handler validation works.
radio = fallback(track_sensitive=false, [queue, bumpers, mksafe(fallback_playlist)])

# Volume normalization
enable_replaygain_metadata()
radio = amplify(1., override="replaygain_track_gain", radio)

# ---------------------------------------------------------------------------
# Icecast Output
# ---------------------------------------------------------------------------

output.icecast(
  %mp3(bitrate=128, samplerate=44100),
  host="icecast",
  port=8000,
  password=environment.get("ICECAST_SOURCE_PASSWORD", default="hackme"),
  mount="/stream.mp3",
  name="Tramontane Radio",
  description="AI-powered radio station",
  send_icy_metadata=true,
  radio
)

# ---------------------------------------------------------------------------
# Harbor HTTP API (port 8080)
# ---------------------------------------------------------------------------

# POST /push - Push a track path into the request queue
def push_handler(request, response) =
  body = request.body()
  uri = string.trim(body)
  if string.match(pattern="^/music/", uri) then
    result = server.execute("queue.push #{uri}")
    response.json({status = "ok", result = result})
  else
    response.json({status = "error", message = "Path must be under /music"})
  end
end

harbor.http.register(
  port=8080,
  method="POST",
  "/push",
  push_handler
)

# GET /now-playing - Get current queue metadata
def now_playing_handler(_, response) =
  meta = server.execute("queue.metadata")
  response.json({metadata = meta})
end

harbor.http.register(
  port=8080,
  method="GET",
  "/now-playing",
  now_playing_handler
)

# POST /flush - Clear the request queue and skip current track
def flush_handler(_, response) =
  ignore(server.execute("queue.flush_and_skip"))
  response.json({status = "ok", message = "Queue flushed"})
end

harbor.http.register(
  port=8080,
  method="POST",
  "/flush",
  flush_handler
)

# GET /queue-status - Queue depth + current track timing
def queue_status_handler(_, response) =
  result = server.execute("queue.queue")
  pending = string.concat(separator="\n", result)
  trimmed = string.trim(pending)
  n = if trimmed == "" then 0 else list.length(string.split(separator="\n", trimmed)) end
  rem = queue.remaining()
  elapsed = queue.elapsed()
  dur = queue.duration()
  response.json({length = n, remaining = rem, elapsed = elapsed, duration = dur})
end

harbor.http.register(
  port=8080,
  method="GET",
  "/queue-status",
  queue_status_handler
)
