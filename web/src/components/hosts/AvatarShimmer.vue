<template>
  <div class="relative overflow-hidden" :class="size">
    <Transition name="avatar-fade" mode="out-in">
      <!-- Complete: show actual avatar -->
      <img
        v-if="avatarStatus === 'complete' && avatarUrl"
        :key="'img'"
        :src="avatarUrl"
        alt="Host avatar"
        class="rounded-lg object-cover w-full h-full"
      />

      <!-- Generating / Pending: shimmer placeholder -->
      <div
        v-else-if="avatarStatus === 'pending' || avatarStatus === 'generating'"
        :key="'shimmer'"
        class="rounded-lg bg-dark-accent w-full h-full flex items-center justify-center shimmer-bg"
      >
        <span class="font-pixel text-[6px] text-gray-400 animate-pulse">
          {{ avatarStatus === 'generating' ? 'GENERATING...' : 'WAITING...' }}
        </span>
      </div>

      <!-- Failed / Skipped: fallback placeholder -->
      <div
        v-else
        :key="'fallback'"
        class="rounded-lg bg-dark-accent w-full h-full flex flex-col items-center justify-center gap-1"
      >
        <!-- Pixel robot icon -->
        <svg viewBox="0 0 16 16" class="w-6 h-6 text-gray-500" fill="currentColor">
          <rect x="3" y="2" width="10" height="8" rx="1" />
          <rect x="5" y="4" width="2" height="2" fill="#1a1a2e" />
          <rect x="9" y="4" width="2" height="2" fill="#1a1a2e" />
          <rect x="6" y="7" width="4" height="1" fill="#1a1a2e" />
          <rect x="4" y="11" width="3" height="3" />
          <rect x="9" y="11" width="3" height="3" />
          <rect x="7" y="0" width="2" height="2" />
        </svg>
        <span class="font-pixel text-[6px] text-gray-500">NO AVATAR</span>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  avatarUrl: string | null
  avatarStatus: string
  size?: string
}>()
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

.avatar-fade-enter-active,
.avatar-fade-leave-active {
  transition: opacity 0.3s ease;
}

.avatar-fade-enter-from,
.avatar-fade-leave-to {
  opacity: 0;
}
</style>
