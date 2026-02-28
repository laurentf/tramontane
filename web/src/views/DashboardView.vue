<template>
  <div class="p-6 space-y-8">
    <!-- Welcome -->
    <div class="text-center space-y-2 pt-4">
      <p class="text-gray-400 text-sm">Welcome back, {{ displayName }}</p>
    </div>

    <!-- Radio player -->
    <div class="flex justify-center">
      <RadioPlayer />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import RadioPlayer from '@/components/radio/RadioPlayer.vue'

const authStore = useAuthStore()

const displayName = computed(() => {
  return authStore.user?.display_name || authStore.user?.email?.split('@')[0] || 'user'
})
</script>
