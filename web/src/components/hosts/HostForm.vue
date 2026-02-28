<template>
  <form @submit.prevent="handleSubmit" class="space-y-5">
    <!-- Host Name -->
    <div class="space-y-1">
      <label for="host-name" class="font-pixel text-[8px] text-gray-400 uppercase block">
        {{ t('hosts.hostName') }}
      </label>
      <input
        id="host-name"
        v-model="formData.name"
        type="text"
        maxlength="50"
        required
        :placeholder="t('hosts.hostNamePlaceholder')"
        class="w-full bg-dark-bg border rounded px-3 py-2 text-white font-pixel text-xs focus:border-neon-blue outline-none transition-colors"
        :class="nameError ? 'border-neon-pink' : 'border-dark-accent'"
      />
      <p v-if="nameError" class="font-pixel text-[6px] text-neon-pink">
        {{ nameError }}
      </p>
    </div>

    <!-- Dynamic questionnaire fields -->
    <div v-if="fields.length" class="space-y-4">
      <div v-for="field in fields" :key="field.field_key" class="space-y-1">
        <label :for="'field-' + field.field_key" class="font-pixel text-[8px] text-gray-400 uppercase block">
          {{ field.label }}
          <span v-if="field.required" class="text-neon-pink">*</span>
        </label>

        <!-- Select -->
        <select
          v-if="field.field_type === 'select'"
          :id="'field-' + field.field_key"
          v-model="dynamicData[field.field_key]"
          class="w-full bg-dark-bg border border-dark-accent rounded px-3 py-2 text-white font-pixel text-xs focus:border-neon-blue outline-none transition-colors"
        >
          <option value="" disabled>--</option>
          <option
            v-for="opt in field.options"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </option>
        </select>

        <!-- Multi-select (checkboxes) -->
        <div v-else-if="field.field_type === 'multi_select'" class="flex flex-wrap gap-2">
          <label
            v-for="opt in field.options"
            :key="opt.value"
            class="flex items-center gap-1 px-2 py-1 rounded border text-xs cursor-pointer transition-colors"
            :class="isSelected(field.field_key, opt.value)
              ? 'border-neon-purple bg-neon-purple/20 text-white'
              : 'border-dark-accent text-gray-400 hover:border-neon-purple/50'"
          >
            <input
              type="checkbox"
              :value="opt.value"
              :checked="isSelected(field.field_key, opt.value)"
              class="sr-only"
              @change="toggleMulti(field.field_key, opt.value, field.max_select ?? 99)"
            />
            <span class="font-pixel text-[8px]">{{ opt.label }}</span>
          </label>
        </div>

        <!-- Text -->
        <input
          v-else-if="field.field_type === 'text'"
          :id="'field-' + field.field_key"
          v-model="dynamicData[field.field_key]"
          type="text"
          :maxlength="field.max_length ?? 200"
          :placeholder="field.placeholder ?? ''"
          class="w-full bg-dark-bg border border-dark-accent rounded px-3 py-2 text-white font-pixel text-xs focus:border-neon-blue outline-none transition-colors"
        />

        <!-- Textarea -->
        <textarea
          v-else-if="field.field_type === 'textarea'"
          :id="'field-' + field.field_key"
          v-model="dynamicData[field.field_key]"
          :maxlength="field.max_length ?? 400"
          rows="3"
          :placeholder="field.placeholder ?? ''"
          class="w-full bg-dark-bg border border-dark-accent rounded px-3 py-2 text-white font-pixel text-xs focus:border-neon-blue outline-none resize-none transition-colors"
        />
      </div>
    </div>

    <!-- Submit -->
    <button
      type="submit"
      :disabled="submitting"
      class="w-full font-pixel text-xs bg-neon-purple text-white px-4 py-3 rounded shadow-pixel hover:brightness-110 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {{ submitting ? t('hosts.summoning') : t('hosts.summonHost') }}
    </button>
  </form>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '@/lib/api'
import type { HostCreate } from '@/stores/hosts'

interface FieldOption {
  value: string
  label: string
}

interface QuestionnaireField {
  field_key: string
  field_type: string
  required: boolean
  label: string
  placeholder?: string
  min_length?: number
  max_length?: number
  min_select?: number
  max_select?: number
  options?: FieldOption[]
}

const props = defineProps<{
  templateId: string
}>()

const emit = defineEmits<{
  submit: [data: HostCreate]
}>()

const { t, locale } = useI18n()

const submitting = ref(false)
const nameError = ref<string | null>(null)
const fields = ref<QuestionnaireField[]>([])

const formData = reactive({ name: '' })
const dynamicData = reactive<Record<string, string | string[]>>({})

onMounted(async () => {
  try {
    const resp = await api.get<{ template_id: string; fields: QuestionnaireField[] }>(
      `/api/v1/hosts/templates/${props.templateId}/questionnaire?locale=${locale.value}`
    )
    fields.value = resp.fields
    // Initialize defaults
    for (const f of resp.fields) {
      if (f.field_type === 'multi_select') {
        dynamicData[f.field_key] = []
      } else {
        dynamicData[f.field_key] = ''
      }
    }
  } catch {
    // Questionnaire fetch failed — form will just have the name field
  }
})

function isSelected(fieldKey: string, value: string): boolean {
  const arr = dynamicData[fieldKey]
  return Array.isArray(arr) && arr.includes(value)
}

function toggleMulti(fieldKey: string, value: string, maxSelect: number) {
  const arr = dynamicData[fieldKey] as string[]
  const idx = arr.indexOf(value)
  if (idx >= 0) {
    arr.splice(idx, 1)
  } else if (arr.length < maxSelect) {
    arr.push(value)
  }
}

function handleSubmit() {
  nameError.value = null

  if (!formData.name.trim()) {
    nameError.value = t('hosts.nameRequired')
    return
  }

  submitting.value = true

  // Build description from dynamic fields
  const description: Record<string, unknown> = {}
  for (const [key, val] of Object.entries(dynamicData)) {
    if (val !== '' && !(Array.isArray(val) && val.length === 0)) {
      description[key] = val
    }
  }

  emit('submit', {
    name: formData.name.trim(),
    template_id: props.templateId,
    description,
  })
}

defineExpose({ submitting })
</script>
