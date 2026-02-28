<template>
  <div class="flex flex-col h-full bg-dark-bg">
    <!-- Top bar: title only -->
    <header class="bg-dark-surface border-b border-dark-accent px-4 py-3 flex items-center justify-center">
      <span class="font-pixel text-sm text-neon-blue">TRAMONTANE</span>
    </header>

    <!-- Main content area -->
    <main class="flex-1 overflow-y-auto max-w-screen-lg mx-auto w-full">
      <RouterView />
    </main>

    <!-- Bottom tab bar navigation -->
    <nav class="bg-dark-surface border-t border-dark-accent">
      <div class="flex justify-around items-center max-w-screen-lg mx-auto">
        <RouterLink
          to="/"
          class="flex-1 flex flex-col items-center py-2 gap-1 transition-colors"
          :class="isActive('/') ? 'text-neon-blue' : 'text-gray-400 hover:text-neon-blue'"
        >
          <PixelIcon name="home" size="lg" />
          <span class="text-[8px] font-pixel">{{ t('nav.dashboard') }}</span>
        </RouterLink>

        <RouterLink
          to="/hosts"
          class="flex-1 flex flex-col items-center py-2 gap-1 transition-colors"
          :class="isActive('/hosts') ? 'text-neon-blue' : 'text-gray-400 hover:text-neon-blue'"
        >
          <PixelIcon name="user" size="lg" />
          <span class="text-[8px] font-pixel">{{ t('nav.hosts') }}</span>
        </RouterLink>

        <RouterLink
          v-if="authStore.isAdmin"
          to="/schedule"
          class="flex-1 flex flex-col items-center py-2 gap-1 transition-colors"
          :class="isActive('/schedule') ? 'text-neon-blue' : 'text-gray-400 hover:text-neon-blue'"
        >
          <PixelIcon name="briefcase" size="lg" />
          <span class="text-[8px] font-pixel">{{ t('nav.schedule') }}</span>
        </RouterLink>

        <RouterLink
          v-if="authStore.isAdmin"
          to="/settings"
          class="flex-1 flex flex-col items-center py-2 gap-1 transition-colors"
          :class="isActive('/settings') ? 'text-neon-blue' : 'text-gray-400 hover:text-neon-blue'"
        >
          <PixelIcon name="sliders" size="lg" />
          <span class="text-[8px] font-pixel">{{ t('nav.settings') }}</span>
        </RouterLink>

      </div>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import PixelIcon from '@/components/ui/PixelIcon.vue'

const route = useRoute()
const { t } = useI18n()
const authStore = useAuthStore()

function isActive(path: string) {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}
</script>
