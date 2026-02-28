<template>
  <div class="p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-3">
      <router-link
        to="/hosts"
        class="font-pixel text-xs text-gray-400 hover:text-neon-blue transition-colors"
      >
        &lt; {{ t('hosts.back') }}
      </router-link>
      <h1 class="font-pixel text-sm text-neon-blue flex-1">{{ t('hosts.detailTitle') }}</h1>
    </div>

    <!-- Not found -->
    <div v-if="notFound" class="text-center py-16 space-y-4">
      <p class="font-pixel text-xs text-neon-pink">{{ t('hosts.notFound') }}</p>
      <router-link
        to="/hosts"
        class="font-pixel text-[8px] text-neon-blue underline hover:text-neon-purple transition-colors"
      >
        {{ t('hosts.backToList') }}
      </router-link>
    </div>

    <!-- Loading -->
    <div v-else-if="!hostStore.currentHost && !hostStore.error" class="text-center py-16">
      <p class="font-pixel text-xs text-gray-400 animate-pulse">{{ t('hosts.loading') }}</p>
    </div>

    <!-- Host detail -->
    <template v-else-if="hostStore.currentHost">
      <div class="flex flex-col items-center gap-4">
        <!-- Avatar -->
        <AvatarShimmer
          :avatar-url="resolveAvatarUrl(hostStore.currentHost.id, hostStore.currentHost.avatar_url, hostStore.currentHost.updated_at)"
          :avatar-status="hostStore.currentHost.avatar_status"
          size="w-40 h-40"
        />

        <!-- Name -->
        <h2 class="font-pixel text-lg text-neon-blue text-center">
          {{ hostStore.currentHost.name }}
        </h2>
      </div>

      <!-- Summary -->
      <div class="bg-dark-surface border border-dark-accent rounded-lg p-4 space-y-1">
        <label class="font-pixel text-[8px] text-gray-400 uppercase">
          {{ t('hosts.summary') }}
        </label>
        <p class="text-xs text-white leading-relaxed">
          {{ hostStore.currentHost.short_summary || t('hosts.noSummary') }}
        </p>
      </div>

      <!-- Self description -->
      <div class="bg-dark-surface border border-dark-accent rounded-lg p-4 space-y-1">
        <label class="font-pixel text-[8px] text-gray-400 uppercase">
          {{ t('hosts.selfDescription') }}
        </label>
        <p class="text-xs text-white leading-relaxed whitespace-pre-line">
          {{ hostStore.currentHost.self_description || t('hosts.noSelfDescription') }}
        </p>
      </div>
    </template>

    <!-- Error -->
    <div v-if="hostStore.error && !notFound" class="text-center">
      <p class="font-pixel text-[8px] text-neon-pink">{{ hostStore.error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useHostStore, resolveAvatarUrl } from '@/stores/hosts'
import AvatarShimmer from '@/components/hosts/AvatarShimmer.vue'

const props = defineProps<{
  id: string
}>()

const { t } = useI18n()
const hostStore = useHostStore()
const notFound = ref(false)

onMounted(async () => {
  await hostStore.fetchHost(props.id)
  if (!hostStore.currentHost && hostStore.error) {
    notFound.value = true
  }
})
</script>
