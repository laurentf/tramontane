import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/lib/api'

// --- Types matching backend schemas ---

export interface Host {
  id: string
  name: string
  template_id: string
  short_summary: string | null
  self_description: string | null
  avatar_url: string | null
  avatar_status: string // pending | generating | complete | failed | skipped
  voice_id: string | null
  status: string // draft | active | archived
  created_at: string
  updated_at: string
}

export interface Template {
  template_id: string
  name: string
  description: string
  icon: string
}

export interface HostCreate {
  name: string
  template_id: string
  description?: Record<string, unknown>
}

export interface HostUpdate {
  name?: string
  status?: string
}

export interface EnrichmentResult {
  short_summary: string
  self_description: string
  avatar_prompt: string
}

const API_BASE = import.meta.env.VITE_API_URL || ''

/**
 * Resolve a host avatar URL: storage paths go through the proxy endpoint,
 * HTTP URLs (legacy/fallback) are used as-is.
 */
export function resolveAvatarUrl(hostId: string, avatarUrl: string | null, updatedAt?: string): string | null {
  if (!avatarUrl) return null
  if (avatarUrl.startsWith('http')) return avatarUrl
  const cacheBust = updatedAt ? `?v=${new Date(updatedAt).getTime()}` : ''
  return `${API_BASE}/api/v1/hosts/${hostId}/avatar${cacheBust}`
}

export const useHostStore = defineStore('hosts', () => {
  const hosts = ref<Host[]>([])
  const templates = ref<Template[]>([])
  const currentHost = ref<Host | null>(null)
  const loading = ref(false)
  const enriching = ref(false)
  const enrichmentResult = ref<EnrichmentResult | null>(null)
  const error = ref<string | null>(null)

  async function fetchTemplates(locale?: string) {
    error.value = null
    const params = locale ? `?locale=${locale}` : ''
    try {
      templates.value = await api.get<Template[]>(`/api/v1/hosts/templates${params}`)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch templates'
    }
  }

  async function fetchHosts() {
    error.value = null
    loading.value = true
    try {
      hosts.value = await api.get<Host[]>('/api/v1/hosts')
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch hosts'
    } finally {
      loading.value = false
    }
  }

  async function fetchHost(id: string) {
    error.value = null
    try {
      const host = await api.get<Host>(`/api/v1/hosts/${id}`)
      currentHost.value = host
      // Sync back to the list array
      const idx = hosts.value.findIndex((h) => h.id === id)
      if (idx !== -1) {
        hosts.value[idx] = host
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch host'
    }
  }

  async function createHost(data: HostCreate): Promise<Host | null> {
    error.value = null
    try {
      const host = await api.post<Host>('/api/v1/hosts', data)
      hosts.value.unshift(host)
      currentHost.value = host
      return host
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to create host'
      return null
    }
  }

  async function updateHost(id: string, data: HostUpdate): Promise<Host | null> {
    error.value = null
    try {
      const host = await api.patch<Host>(`/api/v1/hosts/${id}`, data)
      const idx = hosts.value.findIndex((h) => h.id === id)
      if (idx !== -1) {
        hosts.value[idx] = host
      }
      currentHost.value = host
      return host
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update host'
      return null
    }
  }

  async function deleteHost(id: string): Promise<boolean> {
    error.value = null
    try {
      await api.delete(`/api/v1/hosts/${id}`)
      hosts.value = hosts.value.filter((h) => h.id !== id)
      if (currentHost.value?.id === id) {
        currentHost.value = null
      }
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to delete host'
      return false
    }
  }

  async function enrichHost(id: string) {
    error.value = null
    enriching.value = true
    enrichmentResult.value = null
    try {
      const result = await api.post<EnrichmentResult>(`/api/v1/hosts/${id}/enrich`)
      enrichmentResult.value = result
      // Re-fetch host to get updated fields
      await fetchHost(id)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to enrich host'
    } finally {
      enriching.value = false
    }
  }

  async function regenerateAvatar(id: string) {
    error.value = null
    try {
      await api.post(`/api/v1/hosts/${id}/regenerate-avatar`)
      await fetchHost(id)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to regenerate avatar'
    }
  }

  function pollAvatarStatus(id: string) {
    const maxDuration = 60_000
    const interval = 3_000
    const start = Date.now()

    const timer = setInterval(async () => {
      if (Date.now() - start >= maxDuration) {
        clearInterval(timer)
        return
      }

      await fetchHost(id)
      const status = currentHost.value?.avatar_status
      if (status === 'complete' || status === 'failed') {
        clearInterval(timer)
      }
    }, interval)

    return timer
  }

  function clearEnrichment() {
    enrichmentResult.value = null
  }

  return {
    hosts,
    templates,
    currentHost,
    loading,
    enriching,
    enrichmentResult,
    error,
    fetchTemplates,
    fetchHosts,
    fetchHost,
    createHost,
    updateHost,
    deleteHost,
    enrichHost,
    regenerateAvatar,
    pollAvatarStatus,
    clearEnrichment,
  }
})
