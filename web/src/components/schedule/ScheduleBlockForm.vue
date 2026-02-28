<template>
  <div class="bg-dark-surface border border-dark-accent rounded-lg p-4 space-y-4">
    <!-- Block name -->
    <div>
      <label class="font-pixel text-[8px] text-gray-400 block mb-1">{{ t('schedule.blockName') }}</label>
      <input
        v-model="form.name"
        type="text"
        maxlength="100"
        :placeholder="t('schedule.blockNamePlaceholder')"
        class="w-full bg-dark-bg border border-dark-accent rounded px-3 py-2 text-sm text-gray-200
               focus:border-neon-blue focus:outline-none"
      />
    </div>

    <!-- Host select -->
    <div>
      <label class="font-pixel text-[8px] text-gray-400 block mb-1">{{ t('schedule.assignHost') }}</label>
      <select
        v-model="form.host_id"
        class="w-full bg-dark-bg border border-dark-accent rounded px-3 py-2 text-sm text-gray-200
               focus:border-neon-blue focus:outline-none"
      >
        <option value="" disabled>{{ t('schedule.selectHost') }}</option>
        <option
          v-for="host in hosts"
          :key="host.id"
          :value="host.id"
        >
          {{ host.name }} ({{ host.template_id }})
        </option>
      </select>
    </div>

    <!-- Description / brief -->
    <div>
      <label class="font-pixel text-[8px] text-gray-400 block mb-1">{{ t('schedule.brief') }}</label>
      <textarea
        v-model="form.description"
        maxlength="1000"
        rows="3"
        :placeholder="t('schedule.briefPlaceholder')"
        class="w-full bg-dark-bg border border-dark-accent rounded px-3 py-2 text-sm text-gray-200
               focus:border-neon-blue focus:outline-none resize-none"
      />
    </div>

    <!-- Time range -->
    <div class="grid grid-cols-2 gap-3">
      <div>
        <label class="font-pixel text-[8px] text-gray-400 block mb-1">{{ t('schedule.startTime') }}</label>
        <input
          v-model="form.start_time"
          type="time"
          class="w-full bg-dark-bg border border-dark-accent rounded px-3 py-2 text-sm text-gray-200
                 focus:border-neon-blue focus:outline-none"
        />
      </div>
      <div>
        <label class="font-pixel text-[8px] text-gray-400 block mb-1">{{ t('schedule.endTime') }}</label>
        <input
          v-model="form.end_time"
          type="time"
          class="w-full bg-dark-bg border border-dark-accent rounded px-3 py-2 text-sm text-gray-200
                 focus:border-neon-blue focus:outline-none"
        />
      </div>
    </div>

    <!-- Quick duration buttons -->
    <div class="flex items-center gap-2">
      <span class="font-pixel text-[7px] text-gray-500">{{ t('schedule.quickDuration') }}</span>
      <button
        v-for="preset in durationPresets"
        :key="preset.minutes"
        type="button"
        @click="applyDuration(preset.minutes)"
        :disabled="!form.start_time"
        class="px-2 py-1 rounded font-pixel text-[7px] border transition-colors
               bg-dark-bg border-dark-accent text-gray-400 hover:border-gray-500
               disabled:opacity-30 disabled:cursor-not-allowed"
      >
        {{ preset.label }}
      </button>
      <span v-if="durationDisplay" class="font-pixel text-[7px] text-neon-blue ml-auto">
        = {{ durationDisplay }}
      </span>
    </div>

    <!-- Error display -->
    <div v-if="formError" class="bg-neon-pink/10 border border-neon-pink/30 rounded p-2">
      <p class="font-pixel text-[8px] text-neon-pink">{{ formError }}</p>
    </div>

    <!-- Actions -->
    <div class="flex justify-end gap-3 pt-2">
      <button
        type="button"
        @click="$emit('cancel')"
        class="font-pixel text-[8px] text-gray-400 hover:text-gray-200 transition-colors px-4 py-2"
      >
        {{ t('schedule.cancel') }}
      </button>
      <button
        type="button"
        @click="handleSubmit"
        :disabled="!isValid"
        class="font-pixel text-[8px] bg-neon-purple text-white px-4 py-2 rounded
               hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
      >
        {{ editMode ? t('schedule.updateBlock') : t('schedule.createBlock') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Host } from '@/stores/hosts'
import type { ScheduleBlockCreate } from '@/stores/schedule'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    initialData?: Partial<ScheduleBlockCreate>
    hosts: Host[]
    editMode?: boolean
    serverError?: string | null
  }>(),
  {
    editMode: false,
    serverError: null,
  }
)

const emit = defineEmits<{
  submit: [data: ScheduleBlockCreate]
  cancel: []
}>()

const durationPresets = [
  { label: '5 MIN', minutes: 5 },
  { label: '30 MIN', minutes: 30 },
  { label: '1H', minutes: 60 },
  { label: '2H', minutes: 120 },
]

const form = ref<ScheduleBlockCreate>({
  host_id: props.initialData?.host_id ?? '',
  name: props.initialData?.name ?? '',
  description: props.initialData?.description ?? '',
  start_time: props.initialData?.start_time ?? '',
  end_time: props.initialData?.end_time ?? '',
  day_of_week: props.initialData?.day_of_week ?? null,
  is_active: props.initialData?.is_active ?? true,
})

const formError = ref<string | null>(null)

// Sync serverError into formError
watch(
  () => props.serverError,
  (val) => {
    if (val) formError.value = val
  }
)

function addMinutesToTime(time: string, minutes: number): string {
  const [h, m] = time.split(':').map(Number)
  const total = h * 60 + m + minutes
  const endH = Math.floor(total / 60) % 24
  const endM = total % 60
  return `${String(endH).padStart(2, '0')}:${String(endM).padStart(2, '0')}`
}

function applyDuration(minutes: number) {
  if (!form.value.start_time) return
  form.value.end_time = addMinutesToTime(form.value.start_time, minutes)
}

const isValid = computed(() => {
  return (
    form.value.name.trim().length > 0 &&
    form.value.description.trim().length > 0 &&
    form.value.host_id !== '' &&
    form.value.start_time !== '' &&
    form.value.end_time !== '' &&
    form.value.end_time > form.value.start_time
  )
})

const durationDisplay = computed(() => {
  if (!form.value.start_time || !form.value.end_time) return ''
  if (form.value.end_time <= form.value.start_time) return ''
  const [sh, sm] = form.value.start_time.split(':').map(Number)
  const [eh, em] = form.value.end_time.split(':').map(Number)
  const mins = (eh * 60 + em) - (sh * 60 + sm)
  if (mins <= 0) return ''
  const hours = Math.floor(mins / 60)
  const rem = mins % 60
  if (hours === 0) return `${rem}min`
  if (rem === 0) return `${hours}h`
  return `${hours}h${rem.toString().padStart(2, '0')}`
})

function handleSubmit() {
  formError.value = null
  if (!isValid.value) return
  emit('submit', { ...form.value })
}
</script>
