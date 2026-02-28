import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/lib/api'

// --- Types ---

export interface ScheduleBlock {
  id: string
  host_id: string
  host_name: string | null
  host_avatar_url: string | null
  host_template_id: string | null
  name: string
  description: string
  start_time: string // HH:MM
  end_time: string // HH:MM
  day_of_week: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ScheduleBlockCreate {
  host_id: string
  name: string
  description: string
  start_time: string
  end_time: string
  day_of_week?: number | null
  is_active?: boolean
}

export interface ActiveBlock {
  block: ScheduleBlock | null
  host_name: string | null
  host_avatar_url: string | null
}

export const useScheduleStore = defineStore('schedule', () => {
  const blocks = ref<ScheduleBlock[]>([])
  const activeBlock = ref<ActiveBlock | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // --- Computed ---

  const sortedBlocks = computed(() =>
    [...blocks.value].sort((a, b) => a.start_time.localeCompare(b.start_time))
  )

  // --- Actions ---

  async function fetchBlocks() {
    error.value = null
    loading.value = true
    try {
      blocks.value = await api.get<ScheduleBlock[]>('/api/v1/schedule/blocks')
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch schedule blocks'
    } finally {
      loading.value = false
    }
  }

  async function createBlock(data: ScheduleBlockCreate): Promise<ScheduleBlock | null> {
    error.value = null
    try {
      const block = await api.post<ScheduleBlock>('/api/v1/schedule/blocks', data)
      blocks.value.push(block)
      // Re-sort by start_time
      blocks.value.sort((a, b) => a.start_time.localeCompare(b.start_time))
      return block
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to create schedule block'
      return null
    }
  }

  async function updateBlock(
    id: string,
    data: Partial<ScheduleBlockCreate>
  ): Promise<ScheduleBlock | null> {
    error.value = null
    try {
      const block = await api.patch<ScheduleBlock>(`/api/v1/schedule/blocks/${id}`, data)
      const idx = blocks.value.findIndex((b) => b.id === id)
      if (idx !== -1) {
        blocks.value[idx] = block
      }
      blocks.value.sort((a, b) => a.start_time.localeCompare(b.start_time))
      return block
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update schedule block'
      return null
    }
  }

  async function deleteBlock(id: string): Promise<boolean> {
    error.value = null
    try {
      await api.delete(`/api/v1/schedule/blocks/${id}`)
      blocks.value = blocks.value.filter((b) => b.id !== id)
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to delete schedule block'
      return false
    }
  }

  async function fetchActiveBlock() {
    try {
      activeBlock.value = await api.get<ActiveBlock>('/api/v1/schedule/active', {
        skipAuth: true,
      })
    } catch {
      // Graceful degradation -- player still works without active block info
    }
  }

  return {
    blocks,
    activeBlock,
    loading,
    error,
    sortedBlocks,
    fetchBlocks,
    createBlock,
    updateBlock,
    deleteBlock,
    fetchActiveBlock,
  }
})
