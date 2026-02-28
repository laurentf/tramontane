<template>
  <div>
    <!-- Empty state -->
    <div
      v-if="blocks.length === 0"
      class="flex flex-col items-center justify-center py-12 space-y-6"
    >
      <PixelIcon name="briefcase" size="xl" class="text-neon-purple" />
      <h2 class="font-pixel text-lg text-neon-purple text-center">
        {{ t('schedule.noBlocks') }}
      </h2>
      <p class="text-gray-400 text-center max-w-md">
        {{ t('schedule.noBlocksDescription') }}
      </p>
      <button
        @click="$emit('add')"
        class="font-pixel text-xs bg-neon-purple text-white px-6 py-3 rounded shadow-pixel hover:brightness-110 transition-all"
      >
        {{ t('schedule.createBlock') }}
      </button>
    </div>

    <!-- Calendar day view -->
    <div v-else class="relative select-none" :style="{ height: `${totalHeight}px` }">
      <!-- Hour grid lines -->
      <div
        v-for="hour in visibleHours"
        :key="hour"
        class="absolute left-0 right-0 flex items-start"
        :style="{ top: `${hourToY(hour)}px` }"
      >
        <!-- Time label -->
        <span class="font-pixel text-[7px] text-gray-500 w-10 -mt-1.5 text-right pr-2 flex-shrink-0">
          {{ String(hour).padStart(2, '0') }}:00
        </span>
        <!-- Grid line -->
        <div class="flex-1 border-t border-dark-accent/50"></div>
      </div>

      <!-- Now indicator -->
      <div
        v-if="nowY !== null"
        class="absolute left-10 right-0 flex items-center z-20 pointer-events-none"
        :style="{ top: `${nowY}px` }"
      >
        <div class="w-2 h-2 rounded-full bg-neon-pink -ml-1 flex-shrink-0"></div>
        <div class="flex-1 border-t border-neon-pink/60"></div>
      </div>

      <!-- Clickable background (click to add) -->
      <div
        class="absolute left-10 right-0 top-0 bottom-0 cursor-pointer"
        @click="handleBackgroundClick"
      ></div>

      <!-- Schedule blocks -->
      <div
        v-for="block in blocks"
        :key="block.id"
        class="absolute left-12 right-2 rounded-lg border overflow-hidden cursor-pointer group z-10 transition-all hover:brightness-110"
        :class="[blockBorderColor(block), blockBgColor(block)]"
        :style="blockStyle(block)"
        @click.stop="$emit('edit', block)"
      >
        <div class="p-2 h-full flex flex-col overflow-hidden">
          <!-- Header: time + name -->
          <div class="flex items-center gap-2 flex-shrink-0">
            <span class="font-pixel text-[7px] text-gray-400">
              {{ block.start_time }} - {{ block.end_time }}
            </span>
            <!-- Active indicator -->
            <span
              v-if="isBlockActive(block)"
              class="w-1.5 h-1.5 rounded-full bg-neon-blue animate-pulse flex-shrink-0"
            ></span>
          </div>
          <p class="font-pixel text-[9px] text-gray-200 truncate flex-shrink-0">{{ block.name }}</p>

          <!-- Description (only if tall enough) -->
          <p
            v-if="blockDurationMinutes(block) >= 30"
            class="font-pixel text-[7px] text-gray-500 truncate mt-0.5"
          >
            {{ block.description }}
          </p>

          <!-- Host info (only if tall enough) -->
          <div
            v-if="block.host_name && blockDurationMinutes(block) >= 20"
            class="flex items-center gap-1 mt-auto flex-shrink-0"
          >
            <img
              v-if="block.host_avatar_url"
              :src="block.host_avatar_url"
              :alt="block.host_name"
              class="w-3.5 h-3.5 rounded-full border border-dark-accent object-cover"
            />
            <div
              v-else
              class="w-3.5 h-3.5 rounded-full bg-dark-accent flex items-center justify-center"
            >
              <span class="text-[5px]">&#129302;</span>
            </div>
            <span class="font-pixel text-[7px] text-gray-400">{{ block.host_name }}</span>
          </div>
        </div>

        <!-- Delete button (hover) -->
        <button
          @click.stop="$emit('delete', block)"
          class="absolute top-1 right-1 p-1 text-gray-500 hover:text-neon-pink
                 opacity-0 group-hover:opacity-100 transition-opacity"
          title="Delete"
        >
          <svg viewBox="0 0 16 16" class="w-3 h-3" fill="currentColor">
            <path d="M4.5 3L8 6.5 11.5 3 13 4.5 9.5 8 13 11.5 11.5 13 8 9.5 4.5 13 3 11.5 6.5 8 3 4.5z" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ScheduleBlock } from '@/stores/schedule'
import PixelIcon from '@/components/ui/PixelIcon.vue'

const { t } = useI18n()

defineProps<{
  blocks: ScheduleBlock[]
}>()

const emit = defineEmits<{
  edit: [block: ScheduleBlock]
  delete: [block: ScheduleBlock]
  add: []
  'add-at': [startTime: string]
}>()

// --- Configuration ---
const START_HOUR = 6  // 06:00
const END_HOUR = 26   // 02:00 next day (displayed as 26 for math)
const HOUR_HEIGHT = 60 // px per hour
const totalHeight = computed(() => (END_HOUR - START_HOUR) * HOUR_HEIGHT)

const visibleHours = computed(() => {
  const hours: number[] = []
  for (let h = START_HOUR; h <= END_HOUR; h++) {
    hours.push(h % 24)
  }
  return hours
})

// --- Time math ---
function timeToMinutes(time: string): number {
  const [h, m] = time.split(':').map(Number)
  // Handle hours < START_HOUR as "next day" (e.g., 01:00 = 25*60)
  const adjusted = h < START_HOUR ? h + 24 : h
  return adjusted * 60 + m
}

function hourToY(hour: number): number {
  const adjusted = hour < START_HOUR ? hour + 24 : hour
  return (adjusted - START_HOUR) * HOUR_HEIGHT
}

function minutesToY(minutes: number): number {
  return ((minutes - START_HOUR * 60) / 60) * HOUR_HEIGHT
}

function blockDurationMinutes(block: ScheduleBlock): number {
  return timeToMinutes(block.end_time) - timeToMinutes(block.start_time)
}

// --- Block positioning ---
function blockStyle(block: ScheduleBlock): Record<string, string> {
  const startMin = timeToMinutes(block.start_time)
  const endMin = timeToMinutes(block.end_time)
  const top = minutesToY(startMin)
  const height = Math.max(((endMin - startMin) / 60) * HOUR_HEIGHT, 20)
  return {
    top: `${top}px`,
    height: `${height}px`,
  }
}

// --- Block colors ---
const templateBgMap: Record<string, string> = {
  chill_dj: 'bg-neon-blue/10',
  comedy_host: 'bg-neon-pink/10',
  culture_reviewer: 'bg-neon-purple/10',
  journalist: 'bg-sky-500/10',
}
const templateBorderMap: Record<string, string> = {
  chill_dj: 'border-neon-blue/40',
  comedy_host: 'border-neon-pink/40',
  culture_reviewer: 'border-neon-purple/40',
  journalist: 'border-sky-500/40',
}

function blockBgColor(block: ScheduleBlock): string {
  return templateBgMap[block.host_template_id ?? ''] ?? 'bg-neon-blue/10'
}
function blockBorderColor(block: ScheduleBlock): string {
  return templateBorderMap[block.host_template_id ?? ''] ?? 'border-neon-blue/40'
}

// --- Active block check ---
function isBlockActive(block: ScheduleBlock): boolean {
  const now = new Date()
  const currentMinutes = now.getHours() * 60 + now.getMinutes()
  const [sh, sm] = block.start_time.split(':').map(Number)
  const [eh, em] = block.end_time.split(':').map(Number)
  const blockStart = sh * 60 + sm
  const blockEnd = eh * 60 + em

  if (block.day_of_week != null && block.day_of_week !== now.getDay()) {
    return false
  }
  return block.is_active && currentMinutes >= blockStart && currentMinutes < blockEnd
}

// --- Now indicator ---
const nowMinutes = ref(0)
let nowTimer: ReturnType<typeof setInterval> | null = null

function updateNow() {
  const now = new Date()
  nowMinutes.value = now.getHours() * 60 + now.getMinutes()
}

onMounted(() => {
  updateNow()
  nowTimer = setInterval(updateNow, 60_000)
})
onUnmounted(() => {
  if (nowTimer) clearInterval(nowTimer)
})

const nowY = computed(() => {
  const adjusted = nowMinutes.value < START_HOUR * 60
    ? nowMinutes.value + 24 * 60
    : nowMinutes.value
  if (adjusted < START_HOUR * 60 || adjusted > END_HOUR * 60) return null
  return minutesToY(adjusted)
})

// --- Click to add ---
function handleBackgroundClick(e: MouseEvent) {
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const y = e.clientY - rect.top
  const minutes = START_HOUR * 60 + (y / HOUR_HEIGHT) * 60
  // Snap to 5-minute intervals
  const snapped = Math.round(minutes / 5) * 5
  const h = Math.floor(snapped / 60) % 24
  const m = snapped % 60
  const time = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
  emit('add-at', time)
}
</script>
