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
      <h1 class="font-pixel text-sm text-neon-blue">{{ t('hosts.createTitle') }}</h1>
    </div>

    <!-- Step indicator -->
    <div class="flex items-center justify-center gap-3">
      <div
        v-for="step in 3"
        :key="step"
        class="w-3 h-3 rounded-full transition-colors"
        :class="stepDotClass(step)"
      />
    </div>
    <p class="font-pixel text-[8px] text-gray-500 text-center">{{ stepLabel }}</p>

    <!-- Step content -->
    <Transition :name="transitionName" mode="out-in">
      <!-- Step 1: Template Selection -->
      <div v-if="currentStep === 1" key="step1">
        <TemplateGallery @select="onTemplateSelect" />
      </div>

      <!-- Step 2: Customize -->
      <div v-else-if="currentStep === 2" key="step2" class="space-y-4">
        <button
          type="button"
          @click="goBack"
          class="font-pixel text-[6px] text-gray-400 hover:text-neon-blue transition-colors"
        >
          &lt; {{ t('hosts.changeTemplate') }}
        </button>
        <HostForm
          :template-id="selectedTemplateId!"
          @submit="onFormSubmit"
        />
      </div>

      <!-- Step 3: Enrichment & Save -->
      <div v-else-if="currentStep === 3" key="step3" class="space-y-6">
        <button
          type="button"
          @click="goBack"
          class="font-pixel text-[6px] text-gray-400 hover:text-neon-blue transition-colors"
        >
          &lt; {{ t('hosts.back') }}
        </button>

        <!-- Avatar + Enrichment side by side on larger screens -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <!-- Avatar -->
          <div class="md:col-span-1 flex flex-col items-center gap-2">
            <AvatarShimmer
              :avatar-url="hostStore.currentHost ? resolveAvatarUrl(hostStore.currentHost.id, hostStore.currentHost.avatar_url, hostStore.currentHost.updated_at) : null"
              :avatar-status="hostStore.currentHost?.avatar_status ?? 'pending'"
              size="w-32 h-32"
            />
            <p class="font-pixel text-[6px] text-gray-500">
              {{ avatarStatusText }}
            </p>
          </div>

          <!-- Enrichment reveal -->
          <div class="md:col-span-2">
            <EnrichmentReveal
              :enriching="hostStore.enriching"
              :result="hostStore.enrichmentResult"
              :host="hostStore.currentHost"
              :error="hostStore.error"
              @retry="retryEnrichment"
            />
          </div>
        </div>

        <!-- Activate -->
        <div v-if="hostStore.enrichmentResult && !hostStore.enriching" class="text-center space-y-3">
          <button
            type="button"
            :disabled="saving"
            @click="saveAndActivate"
            class="w-full font-pixel text-xs bg-neon-blue text-white px-6 py-3 rounded shadow-pixel hover:brightness-110 transition-all disabled:opacity-50"
          >
            {{ saving ? t('hosts.saving') : t('hosts.summonHost') }}
          </button>
          <router-link
            to="/hosts"
            class="inline-block font-pixel text-[8px] text-gray-400 hover:text-neon-blue transition-colors underline"
          >
            {{ t('hosts.backToList') }}
          </router-link>
        </div>
      </div>
    </Transition>

    <!-- Global error -->
    <div v-if="hostStore.error && currentStep !== 3" class="text-center">
      <p class="font-pixel text-[8px] text-neon-pink">{{ hostStore.error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useHostStore, resolveAvatarUrl } from '@/stores/hosts'
import type { HostCreate } from '@/stores/hosts'
import TemplateGallery from '@/components/hosts/TemplateGallery.vue'
import HostForm from '@/components/hosts/HostForm.vue'
import EnrichmentReveal from '@/components/hosts/EnrichmentReveal.vue'
import AvatarShimmer from '@/components/hosts/AvatarShimmer.vue'

const router = useRouter()
const hostStore = useHostStore()
const { t } = useI18n()

const currentStep = ref(1)
const selectedTemplateId = ref<string | null>(null)
const createdHostId = ref<string | null>(null)
const saving = ref(false)
const direction = ref<'forward' | 'back'>('forward')

const transitionName = computed(() =>
  direction.value === 'forward' ? 'slide-left' : 'slide-right'
)

const stepLabel = computed(() => {
  switch (currentStep.value) {
    case 1: return t('hosts.step1')
    case 2: return t('hosts.step2')
    case 3: return t('hosts.step3')
    default: return ''
  }
})

const avatarStatusText = computed(() => {
  const status = hostStore.currentHost?.avatar_status
  switch (status) {
    case 'pending': return t('hosts.avatarQueued')
    case 'generating': return t('hosts.avatarGenerating')
    case 'complete': return t('hosts.avatarReady')
    case 'failed': return t('hosts.avatarFailed')
    case 'skipped': return t('hosts.avatarSkipped')
    default: return ''
  }
})

function stepDotClass(step: number) {
  if (step < currentStep.value) return 'bg-neon-blue'
  if (step === currentStep.value) return 'bg-neon-purple'
  return 'bg-dark-accent'
}

function goBack() {
  direction.value = 'back'
  currentStep.value = Math.max(1, currentStep.value - 1)
}

function onTemplateSelect(templateId: string) {
  selectedTemplateId.value = templateId
  direction.value = 'forward'
  currentStep.value = 2
}

async function onFormSubmit(data: HostCreate) {
  const host = await hostStore.createHost(data)
  if (host) {
    createdHostId.value = host.id
    direction.value = 'forward'
    currentStep.value = 3
    // Kick off enrichment
    hostStore.enrichHost(host.id)
    // Start avatar polling (avatar generation triggered by enrichment on backend)
    hostStore.pollAvatarStatus(host.id)
  }
}

function retryEnrichment() {
  if (createdHostId.value) {
    hostStore.enrichHost(createdHostId.value)
  }
}

async function saveAndActivate() {
  if (!createdHostId.value) return
  saving.value = true
  await hostStore.updateHost(createdHostId.value, { status: 'active' })
  saving.value = false

  if (!hostStore.error) {
    hostStore.clearEnrichment()
    router.push({ name: 'hosts' })
  }
}


</script>

<style scoped>
.slide-left-enter-active,
.slide-left-leave-active,
.slide-right-enter-active,
.slide-right-leave-active {
  transition: all 0.3s ease;
}

.slide-left-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.slide-left-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

.slide-right-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}
.slide-right-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
