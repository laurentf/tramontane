import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/lib/api'

export interface RadioSettings {
  station_name: string
  language: string
  location: string
}

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<RadioSettings>({
    station_name: 'Tramontane',
    language: 'fr',
    location: '',
  })
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchSettings() {
    loading.value = true
    error.value = null
    try {
      settings.value = await api.get<RadioSettings>('/api/v1/settings')
    } catch (err: any) {
      error.value = err.message || 'Failed to load settings'
    } finally {
      loading.value = false
    }
  }

  async function updateSettings(data: Partial<RadioSettings>) {
    error.value = null
    try {
      settings.value = await api.patch<RadioSettings>('/api/v1/settings', data)
    } catch (err: any) {
      error.value = err.message || 'Failed to save settings'
    }
  }

  return { settings, loading, error, fetchSettings, updateSettings }
})
