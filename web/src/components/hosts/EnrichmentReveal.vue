<template>
  <div class="space-y-4">
    <!-- Loading state -->
    <div v-if="enriching" class="text-center py-8 space-y-4">
      <p class="font-pixel text-xs text-neon-purple animate-pulse">{{ t('hosts.enriching') }}</p>
      <!-- Retro loading bar -->
      <div class="mx-auto w-48 h-3 bg-dark-bg border border-dark-accent rounded overflow-hidden">
        <div class="h-full bg-neon-purple loading-bar" />
      </div>
      <p class="font-pixel text-[6px] text-gray-500">{{ t('hosts.enrichingHint') }}</p>
    </div>

    <!-- Error state -->
    <div v-else-if="!result && error" class="text-center py-8 space-y-3">
      <p class="font-pixel text-[8px] text-neon-pink">{{ error }}</p>
      <button
        @click="emit('retry')"
        class="font-pixel text-[8px] text-neon-blue border border-neon-blue px-3 py-1 rounded hover:bg-neon-blue/10 transition-colors"
      >
        {{ t('hosts.retry') }}
      </button>
    </div>

    <!-- Reveal fields -->
    <TransitionGroup
      v-else-if="result"
      name="reveal"
      tag="div"
      class="space-y-4"
    >
      <div
        v-for="(field, index) in visibleFields"
        :key="field.key"
        class="bg-dark-surface border border-dark-accent rounded-lg p-3 space-y-1"
        :style="{ transitionDelay: `${index * 200}ms` }"
      >
        <!-- Field header -->
        <div class="flex items-center justify-between">
          <label class="font-pixel text-[8px] text-gray-400 uppercase">
            {{ field.label }}
          </label>
        </div>

        <!-- Display -->
        <p class="text-xs text-white leading-relaxed">
          {{ field.value }}
        </p>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { EnrichmentResult, Host } from '@/stores/hosts'

const { t } = useI18n()

const props = defineProps<{
  enriching: boolean
  result: EnrichmentResult | null
  host: Host | null
  error?: string | null
}>()

const emit = defineEmits<{
  retry: []
}>()

// Stagger reveal: show fields one by one
const revealCount = ref(0)
let revealTimer: ReturnType<typeof setInterval> | null = null

watch(
  () => props.result,
  (newResult) => {
    if (newResult) {
      revealCount.value = 0
      // Stagger the reveal
      revealTimer = setInterval(() => {
        revealCount.value++
        if (revealCount.value >= 2) {
          if (revealTimer) clearInterval(revealTimer)
        }
      }, 300)
    }
  },
  { immediate: true }
)

interface FieldItem {
  key: string
  label: string
  value: string
}

const allFields = computed<FieldItem[]>(() => {
  if (!props.result) return []
  return [
    {
      key: 'short_summary',
      label: t('hosts.summary'),
      value: props.result.short_summary,
    },
    {
      key: 'self_description',
      label: t('hosts.selfDescription'),
      value: props.result.self_description,
    },
  ]
})

const visibleFields = computed(() => {
  return allFields.value.slice(0, revealCount.value)
})
</script>

<style scoped>
.loading-bar {
  width: 30%;
  animation: loading-sweep 1.2s ease-in-out infinite;
}

@keyframes loading-sweep {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(400%); }
}

.reveal-enter-active {
  transition: all 0.4s ease-out;
}

.reveal-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

.reveal-leave-active {
  transition: all 0.2s ease-in;
}

.reveal-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
