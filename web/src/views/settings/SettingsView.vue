<template>
  <div class="flex flex-col h-full overflow-y-auto">
    <div class="flex-1 p-6 max-w-2xl mx-auto w-full space-y-8">
      <h1 class="font-pixel text-sm text-neon-blue">{{ t('settings.title') }}</h1>

      <!-- Language section -->
      <section class="bg-dark-surface border border-dark-accent shadow-pixel p-6 space-y-4">
        <h2 class="font-pixel text-sm text-neon-blue mb-4">{{ t('settings.language') }}</h2>
        <p class="text-sm text-gray-400 mb-4">{{ t('settings.selectLanguage') }}</p>

        <div class="space-y-2">
          <label
            v-for="lang in languages"
            :key="lang.code"
            class="flex items-center gap-3 p-3 border border-dark-accent cursor-pointer transition-colors"
            :class="currentLanguage === lang.code ? 'border-neon-blue bg-neon-blue/10' : 'hover:border-neon-blue/50'"
          >
            <input
              type="radio"
              :value="lang.code"
              v-model="currentLanguage"
              @change="handleLanguageChange"
              class="w-4 h-4 text-neon-blue focus:ring-neon-blue"
            />
            <span class="text-white">{{ lang.nativeName }}</span>
            <span class="text-gray-500 text-sm">({{ lang.name }})</span>
          </label>
        </div>
      </section>

      <!-- Radio Station section -->
      <section class="bg-dark-surface border border-dark-accent shadow-pixel p-6 space-y-4">
        <h2 class="font-pixel text-sm text-neon-blue mb-4">{{ t('settings.radio') }}</h2>

        <!-- Station Name -->
        <div class="space-y-2">
          <div class="text-sm text-gray-400">{{ t('settings.stationName') }}</div>
          <input
            v-model="form.station_name"
            type="text"
            maxlength="100"
            :placeholder="t('settings.stationNamePlaceholder')"
            class="w-full bg-dark-bg border border-dark-accent text-white px-4 py-2 text-sm focus:border-neon-blue focus:outline-none"
            @blur="saveIfChanged"
          />
        </div>

        <!-- Location -->
        <div class="space-y-2">
          <div class="text-sm text-gray-400">{{ t('settings.location') }}</div>
          <input
            v-model="form.location"
            type="text"
            maxlength="200"
            :placeholder="t('settings.locationPlaceholder')"
            class="w-full bg-dark-bg border border-dark-accent text-white px-4 py-2 text-sm focus:border-neon-blue focus:outline-none"
            @blur="saveIfChanged"
          />
        </div>
      </section>

      <!-- Music Library section (admin only) -->
      <section v-if="authStore.isAdmin" class="bg-dark-surface border border-dark-accent shadow-pixel p-6 space-y-4">
        <h2 class="font-pixel text-sm text-neon-blue mb-4">{{ t('settings.musicLibrary') }}</h2>
        <p class="text-sm text-gray-400">{{ t('settings.scanDescription') }}</p>
        <button
          @click="scanMusic"
          :disabled="isScanning"
          class="w-full font-pixel text-xs bg-neon-blue text-white px-6 py-3 shadow-pixel hover:brightness-110 transition-all disabled:opacity-50"
        >
          {{ isScanning ? t('settings.scanning') : t('settings.scanMusic') }}
        </button>
        <p v-if="scanResult" class="font-pixel text-[8px] text-neon-purple text-center">
          {{ scanResult }}
        </p>
        <p v-if="scanError" class="font-pixel text-[8px] text-neon-pink text-center">
          {{ scanError }}
        </p>
      </section>

      <!-- Account section -->
      <section class="bg-dark-surface border border-dark-accent shadow-pixel p-6 space-y-4">
        <h2 class="font-pixel text-sm text-neon-blue mb-4">{{ t('settings.account') }}</h2>

        <div class="space-y-2">
          <div class="text-sm text-gray-400">Email</div>
          <div class="text-white">{{ authStore.user?.email || '—' }}</div>
        </div>

        <div class="pt-4 mt-4 border-t border-dark-accent">
          <button
            @click="handleSignOut"
            :disabled="isSigningOut"
            class="w-full font-pixel text-xs bg-neon-pink text-white px-6 py-3 rounded shadow-pixel hover:brightness-110 transition-all disabled:opacity-50"
          >
            {{ isSigningOut ? '...' : t('auth.signOut') }}
          </button>
        </div>
      </section>

      <!-- Save indicator -->
      <p v-if="settingsStore.error" class="font-pixel text-[8px] text-neon-pink text-center">
        {{ settingsStore.error }}
      </p>
    </div>

    <!-- Sign out confirmation -->
    <Teleport to="body">
      <Transition name="modal-fade">
        <div
          v-if="showSignOutConfirm"
          class="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
          @click.self="showSignOutConfirm = false"
        >
          <div class="bg-dark-surface border-2 border-neon-pink rounded-lg p-6 max-w-sm w-full shadow-pixel space-y-4">
            <p class="font-pixel text-xs text-gray-200 text-center">
              {{ t('settings.signOutConfirm') }}
            </p>
            <div class="flex gap-3 justify-center">
              <button
                @click="showSignOutConfirm = false"
                class="font-pixel text-[8px] text-gray-400 hover:text-neon-blue transition-colors px-4 py-2 border border-dark-accent rounded"
              >
                {{ t('common.cancel') }}
              </button>
              <button
                @click="confirmSignOut"
                class="font-pixel text-[8px] bg-neon-pink text-white px-4 py-2 rounded hover:brightness-110 transition-all"
              >
                {{ t('auth.signOut') }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'
import { api } from '@/lib/api'

const { t, locale } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const settingsStore = useSettingsStore()

const isScanning = ref(false)
const scanResult = ref<string | null>(null)
const scanError = ref<string | null>(null)
const isSigningOut = ref(false)
const showSignOutConfirm = ref(false)
const currentLanguage = ref(locale.value)

const form = reactive({
  station_name: '',
  location: '',
})

const languages = [
  { code: 'en', name: 'English', nativeName: 'English' },
  { code: 'fr', name: 'French', nativeName: 'Francais' },
  { code: 'es', name: 'Spanish', nativeName: 'Espanol' },
]

// Sync form from store
watch(
  () => settingsStore.settings,
  (s) => {
    form.station_name = s.station_name
    form.location = s.location
    currentLanguage.value = s.language
  },
  { immediate: true }
)

onMounted(() => {
  settingsStore.fetchSettings()
})

function handleLanguageChange() {
  // Update i18n locale (changes all translations instantly)
  locale.value = currentLanguage.value
  localStorage.setItem('tramontane-locale', currentLanguage.value)

  // Persist to backend
  settingsStore.updateSettings({ language: currentLanguage.value })
}

function saveIfChanged() {
  const s = settingsStore.settings
  const updates: Record<string, string> = {}
  if (form.station_name !== s.station_name) updates.station_name = form.station_name
  if (form.location !== s.location) updates.location = form.location
  if (Object.keys(updates).length > 0) {
    settingsStore.updateSettings(updates)
  }
}

async function scanMusic() {
  isScanning.value = true
  scanResult.value = null
  scanError.value = null
  try {
    const result = await api.post<{ scanned: number; stored: number }>('/api/v1/ingest/scan', {})
    scanResult.value = t('settings.scanResult', { scanned: result.scanned, stored: result.stored })
  } catch (err) {
    scanError.value = err instanceof Error ? err.message : 'Scan failed'
  } finally {
    isScanning.value = false
  }
}

function handleSignOut() {
  showSignOutConfirm.value = true
}

async function confirmSignOut() {
  showSignOutConfirm.value = false
  isSigningOut.value = true
  try {
    await authStore.signOut()
    router.push('/login')
  } catch (err) {
    console.error('Sign out failed:', err)
    isSigningOut.value = false
  }
}
</script>

<style scoped>
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>
