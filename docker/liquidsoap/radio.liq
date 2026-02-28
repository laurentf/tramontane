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
fallback_playlist = playlist(id="fallback", mode="random", "/music")

# Fallback chain: queue -> library -> silence
radio = fallback(track_sensitive=false, [queue, mksafe(fallback_playlist)])

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
