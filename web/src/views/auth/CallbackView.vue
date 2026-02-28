<template>
  <div class="flex flex-col items-center justify-center min-h-screen bg-dark-bg px-4">
    <div class="text-center space-y-6">
      <!-- Loading state -->
      <div v-if="!error">
        <h1 class="font-pixel text-xl text-neon-purple mb-4">AUTHENTICATING...</h1>
        <div class="flex justify-center">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-neon-purple"></div>
        </div>
        <p class="text-gray-400 text-sm mt-4">Completing sign in</p>
      </div>

      <!-- Error state -->
      <div v-else>
        <h1 class="font-pixel text-xl text-red-400 mb-4">AUTH FAILED</h1>
        <div class="max-w-md p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
          <p class="text-red-400 text-sm">{{ error }}</p>
        </div>
        <button
          @click="returnToLogin"
          class="mt-6 px-6 py-2 bg-neon-purple text-white rounded-lg hover:bg-neon-purple/80 transition-colors"
        >
          Return to Login
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const error = ref<string | null>(null)

function safeRedirect(): string {
  const raw = route.query.redirect
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' && value.startsWith('/') ? value : '/'
}

onMounted(async () => {
  try {
    await authStore.initialize()

    if (authStore.isAuthenticated) {
      router.push(safeRedirect())
    } else {
      error.value = authStore.error || 'Authentication failed. Please try again.'
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Authentication failed. Please try again.'
  }
})

watch(
  () => authStore.isAuthenticated,
  (isAuth) => {
    if (isAuth && !error.value) {
      router.push(safeRedirect())
    }
  }
)

function returnToLogin() {
  router.push('/login')
}
</script>
