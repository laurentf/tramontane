<template>
  <div class="w-72 bg-dark-surface border-2 border-dark-accent shadow-pixel">
    <!-- Screen area -->
    <div class="bg-dark-bg border-b-2 border-dark-accent p-4 space-y-3">
      <!-- Status bar -->
      <div class="flex items-center justify-between">
        <!-- On-air pixel icon -->
        <div class="flex items-center gap-2">
          <div
            class="on-air-icon"
            :class="{
              'on-air-live': playerStore.isPlaying,
              'on-air-error': playerStore.error,
              'on-air-loading': playerStore.isLoading,
            }"
          >
            <!-- 5x5 pixel tower icon -->
            <svg viewBox="0 0 9 9" class="w-3 h-3" fill="currentColor">
              <rect x="4" y="3" width="1" height="6" />
              <rect x="3" y="1" width="1" height="1" />
              <rect x="5" y="1" width="1" height="1" />
              <rect x="2" y="0" width="1" height="1" />
              <rect x="6" y="0" width="1" height="1" />
              <rect x="1" y="2" width="1" height="1" />
              <rect x="7" y="2" width="1" height="1" />
            </svg>
          </div>
        </div>
        <span class="font-pixel text-[8px] text-dark-accent">FM 99.7</span>
      </div>

      <!-- Now playing display -->
      <div class="h-12 flex flex-col justify-center">
        <p
          class="font-pixel text-[10px] text-neon-blue truncate"
          :title="displayTitle"
        >
          {{ displayTitle }}
        </p>
        <p
          class="font-pixel text-[8px] text-neon-purple mt-1 truncate"
          :title="displayArtist"
        >
          {{ displayArtist }}
        </p>
      </div>

      <!-- Visualizer bars -->
      <canvas
        ref="vizCanvas"
        width="240"
        height="16"
        class="w-full h-4 block"
      ></canvas>
    </div>

    <!-- Controls area -->
    <div class="p-4 space-y-4">
      <!-- Play / Stop -->
      <div class="flex justify-center">
        <button
          class="w-12 h-12 border-2 flex items-center justify-center transition-colors
                 focus:outline-none active:translate-x-[2px] active:translate-y-[2px] active:shadow-none"
          :class="buttonClass"
          :disabled="playerStore.isLoading"
          @click="handleToggle"
        >
          <!-- Loading -->
          <span v-if="playerStore.isLoading" class="font-pixel text-[8px] text-neon-blue animate-pulse">...</span>
          <!-- Stop -->
          <svg v-else-if="playerStore.isPlaying" class="w-5 h-5 text-neon-pink" viewBox="0 0 16 16" fill="currentColor">
            <rect x="3" y="3" width="10" height="10" />
          </svg>
          <!-- Play -->
          <svg v-else class="w-5 h-5 text-neon-blue ml-0.5" viewBox="0 0 16 16" fill="currentColor">
            <polygon points="3,1 13,8 3,15" />
          </svg>
        </button>
      </div>

      <!-- Volume -->
      <div class="flex items-center gap-2">
        <span class="font-pixel text-[8px] text-dark-accent">VOL</span>
        <div class="flex-1 relative h-4 flex items-center">
          <input
            type="range"
            min="0"
            max="100"
            :value="Math.round(playerStore.volume * 100)"
            class="pixel-slider w-full"
            aria-label="Volume"
            @input="onVolumeInput"
          />
        </div>
        <span class="font-pixel text-[8px] text-neon-blue w-6 text-right">
          {{ Math.round(playerStore.volume * 100) }}
        </span>
      </div>

      <!-- Error -->
      <div v-if="playerStore.error" class="h-4 flex items-center justify-center">
        <p class="font-pixel text-[8px] text-neon-pink text-center">
          {{ playerStore.error }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { usePlayerStore } from '@/stores/player'

const playerStore = usePlayerStore()
const vizCanvas = ref<HTMLCanvasElement | null>(null)

// Canvas-based visualizer — no DOM thrashing
const BAR_COUNT = 16
const BAR_GAP = 2
const barValues = new Float32Array(BAR_COUNT)
let rafId: number | null = null

function drawBars() {
  const canvas = vizCanvas.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const w = canvas.width
  const h = canvas.height
  const barW = (w - BAR_GAP * (BAR_COUNT - 1)) / BAR_COUNT

  ctx.clearRect(0, 0, w, h)

  if (playerStore.isPlaying) {
    for (let i = 0; i < BAR_COUNT; i++) {
      // Smooth random target
      const target = 0.15 + Math.random() * 0.85
      barValues[i] += (target - barValues[i]) * 0.3
      const barH = Math.max(2, barValues[i] * h)
      ctx.fillStyle = '#00d4ff'
      ctx.fillRect(
        i * (barW + BAR_GAP),
        h - barH,
        barW,
        barH,
      )
    }
    rafId = requestAnimationFrame(drawBars)
  } else {
    for (let i = 0; i < BAR_COUNT; i++) {
      barValues[i] = 0
      ctx.fillStyle = '#2a2a3e'
      ctx.fillRect(i * (barW + BAR_GAP), h - 2, barW, 2)
    }
    rafId = null
  }
}

watch(() => playerStore.isPlaying, (playing) => {
  if (playing && rafId === null) {
    rafId = requestAnimationFrame(drawBars)
  }
})

onMounted(() => { drawBars() })
onUnmounted(() => { if (rafId !== null) cancelAnimationFrame(rafId) })

const displayTitle = computed(() => playerStore.nowPlaying?.title || 'TRAMONTANE RADIO')
const displayArtist = computed(() => playerStore.nowPlaying?.artist || 'TUNE IN')

const buttonClass = computed(() => {
  if (playerStore.isLoading) return 'border-dark-accent bg-dark-bg cursor-wait'
  if (playerStore.isPlaying) return 'border-neon-pink bg-dark-bg shadow-pixel hover:bg-neon-pink/10'
  return 'border-neon-blue bg-dark-bg shadow-pixel hover:bg-neon-blue/10'
})

function handleToggle() {
  if (playerStore.isPlaying) {
    playerStore.stop()
  } else {
    playerStore.play()
  }
}

function onVolumeInput(e: Event) {
  const target = e.target as HTMLInputElement
  playerStore.setVolume(Number(target.value) / 100)
}
</script>

<style scoped>
.on-air-icon {
  color: #9ca3af;
}

.on-air-live {
  color: #4ade80;
}

.on-air-error {
  color: #ff6eb4;
}

.on-air-loading {
  color: #4ade80;
  animation: on-air-pulse 0.8s ease-in-out infinite;
}

@keyframes on-air-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.pixel-slider {
  -webkit-appearance: none;
  appearance: none;
  height: 4px;
  background: #2a2a3e;
  cursor: pointer;
}

.pixel-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 10px;
  height: 10px;
  background: #00d4ff;
  border: none;
  cursor: pointer;
}

.pixel-slider::-moz-range-thumb {
  width: 10px;
  height: 10px;
  background: #00d4ff;
  border: none;
  border-radius: 0;
  cursor: pointer;
}

.pixel-slider::-moz-range-track {
  height: 4px;
  background: #2a2a3e;
}
</style>
