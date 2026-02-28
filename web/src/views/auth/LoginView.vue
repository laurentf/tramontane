<template>
  <div class="flex flex-col items-center justify-center min-h-screen bg-dark-bg px-4">
    <div class="max-w-md w-full space-y-8">
      <!-- App title -->
      <div class="text-center space-y-4">
        <div class="tram-logo">
          <span class="font-pixel text-2xl text-neon-purple">TRAMONTANE</span>
        </div>
        <p class="font-sans text-gray-400 text-sm">Autonomous AI Web Radio</p>
      </div>

      <!-- Google SSO button -->
      <div class="mt-12 flex items-center justify-center">
        <button
          @click="handleGoogleSignIn"
          :disabled="isLoading"
          class="w-14 h-14 flex items-center justify-center bg-dark-surface border-2 border-dark-accent hover:border-neon-blue shadow-pixel hover:shadow-pixel-neon transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <div v-if="isLoading" class="animate-spin rounded-full h-6 w-6 border-b-2 border-neon-blue"></div>
          <svg v-else width="28" height="28" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
          </svg>
        </button>
      </div>

      <!-- Error display -->
      <div v-if="authStore.error" class="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
        <p class="text-red-400 text-sm text-center">{{ authStore.error }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const isLoading = ref(false)

async function handleGoogleSignIn() {
  isLoading.value = true
  try {
    await authStore.signInWithGoogle()
  } catch {
    isLoading.value = false
  }
}
</script>

<style scoped>
@keyframes gentle-bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); }
}
.tram-logo {
  animation: gentle-bounce 2s ease-in-out infinite;
  filter: drop-shadow(0 6px 4px rgba(0, 0, 0, 0.5));
}
</style>
