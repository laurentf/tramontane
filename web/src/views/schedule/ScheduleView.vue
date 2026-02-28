<template>
  <div class="p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h1 class="font-pixel text-sm text-neon-blue">{{ t('schedule.title') }}</h1>
      <button
        @click="toggleForm"
        class="font-pixel text-[8px] bg-neon-purple text-white px-4 py-2 rounded
               hover:bg-neon-purple/80 transition-colors"
      >
        {{ showForm ? t('schedule.close') : t('schedule.addBlock') }}
      </button>
    </div>

    <!-- Add/Edit form -->
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <ScheduleBlockForm
        v-if="showForm"
        :hosts="activeHosts"
        :initial-data="editingBlock ?? undefined"
        :edit-mode="!!editingBlock?._id"
        :server-error="scheduleStore.error"
        @submit="handleFormSubmit"
        @cancel="closeForm"
      />
    </Transition>

    <!-- Error display -->
    <div v-if="scheduleStore.error && !showForm" class="bg-neon-pink/10 border border-neon-pink/30 rounded p-3">
      <p class="font-pixel text-[8px] text-neon-pink">{{ scheduleStore.error }}</p>
    </div>

    <!-- Loading state -->
    <div v-if="scheduleStore.loading" class="space-y-3">
      <div
        v-for="i in 3"
        :key="i"
        class="bg-dark-surface border border-dark-accent rounded-lg p-4 animate-pulse"
      >
        <div class="h-3 bg-dark-accent rounded w-1/3 mb-2"></div>
        <div class="h-2 bg-dark-accent rounded w-1/4"></div>
      </div>
    </div>

    <!-- Timeline -->
    <ScheduleTimeline
      v-else
      :blocks="scheduleStore.sortedBlocks"
      @edit="handleEdit"
      @delete="handleDeleteRequest"
      @add="toggleForm"
      @add-at="handleAddAt"
    />

    <!-- Delete confirmation dialog -->
    <Transition
      enter-active-class="transition-opacity duration-150"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-100"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="deletingBlock"
        class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
        @click.self="deletingBlock = null"
      >
        <div class="bg-dark-surface border border-dark-accent rounded-lg p-6 max-w-sm mx-4 space-y-4">
          <p class="font-pixel text-[10px] text-gray-200">{{ t('schedule.deleteConfirm') }}</p>
          <p class="text-sm text-gray-400">
            {{ t('schedule.deleteWarning', { name: deletingBlock.name }) }}
          </p>
          <div class="flex justify-end gap-3">
            <button
              @click="deletingBlock = null"
              class="font-pixel text-[8px] text-gray-400 hover:text-gray-200 px-4 py-2"
            >
              {{ t('schedule.cancel') }}
            </button>
            <button
              @click="confirmDelete"
              class="font-pixel text-[8px] bg-neon-pink text-white px-4 py-2 rounded
                     hover:brightness-110 transition-all"
            >
              {{ t('schedule.delete') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useScheduleStore } from '@/stores/schedule'
import { useHostStore } from '@/stores/hosts'
import type { ScheduleBlock, ScheduleBlockCreate } from '@/stores/schedule'
import ScheduleTimeline from '@/components/schedule/ScheduleTimeline.vue'
import ScheduleBlockForm from '@/components/schedule/ScheduleBlockForm.vue'

const { t } = useI18n()
const scheduleStore = useScheduleStore()
const hostStore = useHostStore()

const showForm = ref(false)
const editingBlock = ref<Partial<ScheduleBlockCreate> & { _id?: string } | null>(null)
const deletingBlock = ref<ScheduleBlock | null>(null)

const activeHosts = computed(() =>
  hostStore.hosts.filter((h) => h.status === 'active' || h.status === 'draft')
)

onMounted(async () => {
  await Promise.all([scheduleStore.fetchBlocks(), hostStore.fetchHosts()])
})

function toggleForm() {
  if (showForm.value) {
    closeForm()
  } else {
    editingBlock.value = null
    showForm.value = true
  }
}

function handleAddAt(startTime: string) {
  editingBlock.value = { start_time: startTime }
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  editingBlock.value = null
}

function handleEdit(block: ScheduleBlock) {
  editingBlock.value = {
    _id: block.id,
    host_id: block.host_id,
    name: block.name,
    description: block.description,
    start_time: block.start_time,
    end_time: block.end_time,
    day_of_week: block.day_of_week,
    is_active: block.is_active,
  }
  showForm.value = true
}

async function handleFormSubmit(data: ScheduleBlockCreate) {
  if (editingBlock.value?._id) {
    const result = await scheduleStore.updateBlock(editingBlock.value._id, data)
    if (result) closeForm()
  } else {
    const result = await scheduleStore.createBlock(data)
    if (result) closeForm()
  }
}

function handleDeleteRequest(block: ScheduleBlock) {
  deletingBlock.value = block
}

async function confirmDelete() {
  if (!deletingBlock.value) return
  await scheduleStore.deleteBlock(deletingBlock.value.id)
  deletingBlock.value = null
}
</script>
