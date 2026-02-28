<template>
  <div class="p-6 space-y-8">
    <!-- Welcome -->
    <div class="text-center space-y-2 pt-8">
      <h1 class="font-pixel text-xl text-neon-blue">DASHBOARD</h1>
      <p class="text-gray-400 text-sm">Welcome back, {{ displayName }}</p>
    </div>

    <!-- Connection status -->
    <div class="bg-dark-surface border-2 border-dark-accent shadow-pixel p-6 space-y-4">
      <div class="flex items-center gap-3">
        <div class="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
        <span class="font-pixel text-xs text-green-400">CONNECTED</span>
      </div>

      <div class="space-y-3 text-sm">
        <div class="flex justify-between">
          <span class="text-gray-400">Email</span>
          <span class="text-white">{{ authStore.user?.email }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-400">User ID</span>
          <span class="text-white font-mono text-xs">{{ authStore.user?.id.slice(0, 8) }}...</span>
        </div>
      </div>
    </div>

    <!-- Placeholder -->
    <div class="text-center pt-4">
      <p class="text-gray-500 text-xs font-pixel">MORE COMING SOON</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const displayName = computed(() => {
  return authStore.user?.display_name || authStore.user?.email?.split('@')[0] || 'user'
})
</script>
