<template>
  <div class="flex flex-col h-full bg-dark-bg">
    <!-- Top bar -->
    <header class="bg-dark-surface border-b border-dark-accent px-4 py-3 flex items-center justify-between">
      <span class="font-pixel text-sm text-neon-blue">TRAMONTANE</span>
      <button
        @click="handleSignOut"
        class="text-xs text-gray-400 hover:text-neon-pink transition-colors font-pixel"
      >
        LOGOUT
      </button>
    </header>

    <!-- Main content -->
    <main class="flex-1 overflow-y-auto max-w-screen-sm mx-auto w-full">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

function handleSignOut() {
  authStore.signOut()
}
</script>
