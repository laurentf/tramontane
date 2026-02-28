<template>
  <div class="bg-dark-surface border border-dark-accent rounded-lg p-3 flex items-center gap-3 group">
    <!-- Color indicator bar (based on host template) -->
    <div
      class="w-1 self-stretch rounded-full flex-shrink-0"
      :class="templateColor"
    ></div>

    <!-- Content -->
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2">
        <p class="font-pixel text-[10px] text-gray-200 truncate">{{ block.name }}</p>
        <!-- Active indicator -->
        <span
          v-if="isActive"
          class="w-2 h-2 rounded-full bg-neon-blue animate-pulse flex-shrink-0"
          title="Currently on air"
        ></span>
      </div>
      <p class="font-pixel text-[7px] text-gray-500 truncate">{{ block.description }}</p>
      <div class="flex items-center gap-3 mt-1">
        <span class="font-pixel text-[8px] text-gray-400">
          {{ block.start_time }} - {{ block.end_time }}
        </span>
      </div>
      <!-- Host info -->
      <div v-if="block.host_name" class="flex items-center gap-1.5 mt-1.5">
        <img
          v-if="block.host_avatar_url"
          :src="block.host_avatar_url"
          :alt="block.host_name"
          class="w-4 h-4 rounded-full border border-dark-accent object-cover"
        />
        <div
          v-else
          class="w-4 h-4 rounded-full bg-dark-accent flex items-center justify-center"
        >
          <span class="text-[6px]">&#129302;</span>
        </div>
        <span class="font-pixel text-[7px] text-gray-400">{{ block.host_name }}</span>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
      <button
        @click="$emit('edit', block)"
        class="p-1.5 text-gray-400 hover:text-neon-blue transition-colors"
        title="Edit block"
      >
        <svg viewBox="0 0 16 16" class="w-3.5 h-3.5" fill="currentColor">
          <path d="M11.5 1.5l3 3-9 9H2.5v-3l9-9zm-1 2l1 1-7 7H3.5v-1l7-7z" />
        </svg>
      </button>
      <button
        @click="$emit('delete', block)"
        class="p-1.5 text-gray-400 hover:text-neon-pink transition-colors"
        title="Delete block"
      >
        <svg viewBox="0 0 16 16" class="w-3.5 h-3.5" fill="currentColor">
          <path d="M5.5 1v1h-3v2h11V2h-3V1h-5zm-2 4v9h9V5h-9zm3 2h1v5h-1V7zm2 0h1v5h-1V7z" />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ScheduleBlock } from '@/stores/schedule'

const props = defineProps<{
  block: ScheduleBlock
}>()

defineEmits<{
  edit: [block: ScheduleBlock]
  delete: [block: ScheduleBlock]
}>()

const templateColorMap: Record<string, string> = {
  chill_dj: 'bg-neon-blue',
  comedy_host: 'bg-neon-pink',
  culture_reviewer: 'bg-neon-purple',
  journalist: 'bg-neon-blue',
}

const templateColor = computed(() => {
  return templateColorMap[props.block.host_template_id ?? ''] ?? 'bg-neon-blue'
})

const isActive = computed(() => {
  const now = new Date()
  const currentMinutes = now.getHours() * 60 + now.getMinutes()
  const [sh, sm] = props.block.start_time.split(':').map(Number)
  const [eh, em] = props.block.end_time.split(':').map(Number)
  const blockStart = sh * 60 + sm
  const blockEnd = eh * 60 + em

  // Check day of week
  if (props.block.day_of_week != null && props.block.day_of_week !== now.getDay()) {
    return false
  }

  return props.block.is_active && currentMinutes >= blockStart && currentMinutes < blockEnd
})
</script>
