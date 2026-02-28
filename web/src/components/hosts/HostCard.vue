<template>
  <div
    class="bg-dark-surface border border-dark-accent rounded-lg hover:border-neon-blue transition-colors cursor-pointer flex flex-col overflow-hidden relative"
    @click="$router.push({ name: 'host-detail', params: { id: host.id } })"
  >
    <!-- Admin actions overlay -->
    <div v-if="isAdmin" class="absolute top-1.5 right-1.5 z-10 flex gap-1">
      <button
        type="button"
        class="bg-dark-bg/80 rounded p-1 text-gray-400 hover:text-neon-purple transition-colors"
        :title="t('hosts.regenerate')"
        @click.stop="$emit('regenerate', host.id)"
      >
        <PixelIcon name="refresh" size="sm" />
      </button>
      <button
        type="button"
        class="bg-dark-bg/80 rounded p-1 text-gray-400 hover:text-neon-pink transition-colors"
        @click.stop="$emit('delete', host.id)"
      >
        <PixelIcon name="trash" size="sm" />
      </button>
    </div>

    <!-- Avatar -->
    <AvatarShimmer
      :avatar-url="resolveAvatarUrl(host.id, host.avatar_url, host.updated_at)"
      :avatar-status="host.avatar_status"
      size="w-full aspect-square"
    />

    <!-- Info -->
    <div class="px-3 py-2 flex items-center gap-2">
      <PixelIcon :name="templateIcon" size="sm" class="text-neon-purple shrink-0" />
      <p class="font-pixel text-xs text-neon-blue truncate">{{ host.name }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AvatarShimmer from '@/components/hosts/AvatarShimmer.vue'
import PixelIcon from '@/components/ui/PixelIcon.vue'
import { useAuthStore } from '@/stores/auth'
import { resolveAvatarUrl } from '@/stores/hosts'
import type { Host } from '@/stores/hosts'

const { t } = useI18n()

const TEMPLATE_ICONS: Record<string, string> = {
  chill_dj: 'moon-stars',
  comedy_host: 'mood-happy',
  culture_reviewer: 'capitol',
  journalist: 'zap',
}

const props = defineProps<{
  host: Host
}>()

defineEmits<{
  delete: [id: string]
  regenerate: [id: string]
}>()

const authStore = useAuthStore()
const isAdmin = computed(() => authStore.isAdmin)
const templateIcon = computed(() => TEMPLATE_ICONS[props.host.template_id] ?? 'user')
</script>
