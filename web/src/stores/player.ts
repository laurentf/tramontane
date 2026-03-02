import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/lib/api'

export interface NowPlayingDetails {
  title: string
  artist: string
}

interface NowPlayingResponse {
  title: string
  artist: string
  album_art: string | null
  genre: string | null
  listeners: number
}

export const usePlayerStore = defineStore('player', () => {
  const isPlaying = ref(false)
  const isLoading = ref(false)
  const volume = ref(0.8)
  const error = ref<string | null>(null)
  const nowPlaying = ref<NowPlayingDetails | null>(null)

  let audio: HTMLAudioElement | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null

  const streamUrl = computed(() => {
    return import.meta.env.VITE_ICECAST_URL || 'http://localhost:8100/stream.mp3'
  })

  const statusText = computed(() => {
    if (isLoading.value) return 'CONNECTING'
    if (error.value) return 'ERROR'
    if (isPlaying.value) return 'ON AIR'
    return 'READY'
  })

  function getAudio(): HTMLAudioElement {
    if (!audio) {
      audio = new Audio()
      audio.addEventListener('playing', () => {
        isPlaying.value = true
        isLoading.value = false
        error.value = null
      })
      audio.addEventListener('pause', () => {
        isPlaying.value = false
      })
      audio.addEventListener('error', () => {
        isLoading.value = false
        error.value = 'STREAM OFFLINE'
      })
      audio.addEventListener('waiting', () => {
        isLoading.value = true
      })
    }
    return audio
  }

  function play() {
    const el = getAudio()
    isLoading.value = true
    error.value = null
    // Append timestamp to bust browser cache / force fresh connection
    el.src = streamUrl.value + '?t=' + Date.now()
    el.volume = volume.value
    el.play().catch(() => {
      isLoading.value = false
      error.value = 'PLAYBACK FAILED'
    })
    startPolling()
  }

  function stop() {
    if (audio) {
      audio.pause()
      audio.src = ''
    }
    isPlaying.value = false
    isLoading.value = false
    nowPlaying.value = null
    stopPolling()
  }

  function setVolume(vol: number) {
    volume.value = Math.max(0, Math.min(1, vol))
    if (audio) {
      audio.volume = volume.value
    }
  }

  async function fetchNowPlaying() {
    try {
      const data = await api.get<NowPlayingResponse>('/api/v1/radio/now-playing', {
        skipAuth: true,
      })
      if (data) {
        const title = data.title && data.title !== 'Unknown Track' ? data.title : null
        const artist = data.artist && data.artist !== 'Unknown Artist' ? data.artist : null
        nowPlaying.value = title ? { title, artist: artist || '' } : null
      }
    } catch {
      // Graceful degradation — player still works without metadata
    }
  }

  function startPolling() {
    fetchNowPlaying()
    pollTimer = setInterval(fetchNowPlaying, 5000)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  return {
    isPlaying,
    isLoading,
    volume,
    error,
    nowPlaying,
    streamUrl,
    statusText,
    play,
    stop,
    setVolume,
  }
})
