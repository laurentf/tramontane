<template>
  <div class="p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h1 class="font-pixel text-sm text-neon-blue">{{ t('hosts.title') }}</h1>
      <router-link
        v-if="authStore.isAdmin"
        to="/hosts/create"
        class="font-pixel text-[8px] bg-neon-purple text-white px-4 py-2 rounded shadow-pixel hover:brightness-110 transition-all"
      >
        {{ t('hosts.createHost') }}
      </router-link>
    </div>

    <!-- Error state -->
    <div v-if="hostStore.error && !hostStore.loading" class="text-center py-12 space-y-4">
      <p class="font-pixel text-xs text-neon-pink">{{ hostStore.error }}</p>
      <button
        @click="hostStore.fetchHosts()"
        class="font-pixel text-[8px] text-neon-blue border border-neon-blue px-4 py-2 rounded hover:bg-neon-blue/10 transition-colors"
      >
        {{ t('hosts.retry') }}
      </button>
    </div>

    <!-- Loading state -->
    <div v-else-if="hostStore.loading" class="grid grid-cols-2 md:grid-cols-3 gap-4">
      <div
        v-for="n in 3"
        :key="n"
        class="bg-dark-surface border border-dark-accent rounded-lg shadow-pixel overflow-hidden"
      >
        <div class="w-full h-32 bg-dark-accent shimmer-bg" />
        <div class="p-3 space-y-2">
          <div class="h-3 w-20 bg-dark-accent rounded shimmer-bg" />
          <div class="h-2 w-12 bg-dark-accent rounded shimmer-bg" />
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="hostStore.hosts.length === 0"
      class="flex flex-col items-center justify-center py-12 space-y-6"
    >
      <PixelIcon name="user" size="xl" class="text-neon-purple" />
      <h2 class="font-pixel text-lg text-neon-purple text-center">
        {{ t('hosts.noHosts') }}
      </h2>
      <p class="text-gray-400 text-center max-w-md">
        {{ t('hosts.noHostsDescription') }}
      </p>
      <router-link
        v-if="authStore.isAdmin"
        to="/hosts/create"
        class="font-pixel text-xs bg-neon-purple text-white px-6 py-3 rounded shadow-pixel hover:brightness-110 transition-all"
      >
        {{ t('hosts.createHost') }}
      </router-link>
    </div>

    <!-- Host grid -->
    <div v-else class="grid grid-cols-2 md:grid-cols-3 gap-4">
      <HostCard
        v-for="host in hostStore.hosts"
        :key="host.id"
        :host="host"
        @delete="confirmDelete"
        @regenerate="confirmRegenerate"
      />
    </div>

    <!-- Delete confirmation dialog -->
    <Teleport to="body">
      <Transition name="modal-fade">
        <div
          v-if="showDeleteConfirm"
          class="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
          @click.self="showDeleteConfirm = false"
        >
          <div class="bg-dark-surface border-2 border-neon-pink rounded-lg p-6 max-w-sm w-full shadow-pixel space-y-4">
            <h2 class="font-pixel text-xs text-neon-pink text-center">{{ t('hosts.deleteConfirm') }}</h2>
            <p class="text-xs text-gray-300 text-center">{{ t('hosts.deleteWarning') }}</p>
            <p v-if="deleteError" class="font-pixel text-[8px] text-neon-pink text-center">{{ deleteError }}</p>
            <div class="flex gap-3 justify-center">
              <button
                type="button"
                @click="showDeleteConfirm = false"
                class="font-pixel text-[8px] text-gray-400 hover:text-neon-blue transition-colors px-4 py-2 border border-dark-accent rounded"
              >
                {{ t('hosts.cancel') }}
              </button>
              <button
                type="button"
                :disabled="deleting"
                @click="handleDelete"
                class="font-pixel text-[8px] bg-neon-pink text-white px-4 py-2 rounded hover:brightness-110 transition-all disabled:opacity-50"
              >
                {{ deleting ? t('hosts.deleting') : t('hosts.delete') }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Regenerate confirmation dialog -->
    <Teleport to="body">
      <Transition name="modal-fade">
        <div
          v-if="showRegenConfirm"
          class="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
          @click.self="showRegenConfirm = false"
        >
          <div class="bg-dark-surface border-2 border-neon-purple rounded-lg p-6 max-w-sm w-full shadow-pixel space-y-4">
            <h2 class="font-pixel text-xs text-neon-purple text-center">{{ t('hosts.regenConfirm') }}</h2>
            <p class="text-xs text-gray-300 text-center">{{ t('hosts.regenWarning') }}</p>
            <div class="flex gap-3 justify-center">
              <button
                type="button"
                @click="showRegenConfirm = false"
                class="font-pixel text-[8px] text-gray-400 hover:text-neon-blue transition-colors px-4 py-2 border border-dark-accent rounded"
              >
                {{ t('hosts.cancel') }}
              </button>
              <button
                type="button"
                @click="executeRegenerate"
                class="font-pixel text-[8px] bg-neon-purple text-white px-4 py-2 rounded hover:brightness-110 transition-all"
              >
                {{ t('hosts.regenerate') }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useHostStore } from '@/stores/hosts'
import HostCard from '@/components/hosts/HostCard.vue'
import PixelIcon from '@/components/ui/PixelIcon.vue'

const { t } = useI18n()
const authStore = useAuthStore()
const hostStore = useHostStore()

const showDeleteConfirm = ref(false)
const deleteTargetId = ref<string | null>(null)
const deleting = ref(false)
const deleteError = ref<string | null>(null)

const showRegenConfirm = ref(false)
const regenTargetId = ref<string | null>(null)

onMounted(() => {
  hostStore.fetchHosts()
})

function confirmDelete(hostId: string) {
  deleteTargetId.value = hostId
  deleteError.value = null
  showDeleteConfirm.value = true
}

async function handleDelete() {
  if (!deleteTargetId.value) return
  deleting.value = true
  deleteError.value = null
  const success = await hostStore.deleteHost(deleteTargetId.value)
  deleting.value = false
  if (success) {
    showDeleteConfirm.value = false
    deleteTargetId.value = null
  } else {
    deleteError.value = hostStore.error || 'Failed to delete host'
  }
}

function confirmRegenerate(hostId: string) {
  regenTargetId.value = hostId
  showRegenConfirm.value = true
}

async function executeRegenerate() {
  if (!regenTargetId.value) return
  const id = regenTargetId.value
  showRegenConfirm.value = false

  // Optimistic update: show generating state on the card immediately
  const idx = hostStore.hosts.findIndex((h) => h.id === id)
  if (idx !== -1) {
    hostStore.hosts[idx] = { ...hostStore.hosts[idx], avatar_status: 'generating', avatar_url: null }
  }

  await hostStore.regenerateAvatar(id)
  hostStore.pollAvatarStatus(id)
  regenTargetId.value = null
}
</script>

<style scoped>
.shimmer-bg {
  background: linear-gradient(
    90deg,
    #2a2a3e 0%,
    #3a3a5e 40%,
    #2a2a3e 60%,
    #2a2a3e 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>
