<template>
  <div class="space-y-4">
    <!-- Loading -->
    <div v-if="hostStore.templates.length === 0 && !hostStore.error" class="grid grid-cols-2 gap-4">
      <div
        v-for="n in 4"
        :key="n"
        class="bg-dark-surface border-2 border-dark-accent rounded-lg p-4 h-32 shimmer-bg"
      />
    </div>

    <!-- Error -->
    <div v-else-if="hostStore.error" class="text-center py-8">
      <p class="font-pixel text-[8px] text-neon-pink mb-2">{{ hostStore.error }}</p>
      <button
        @click="hostStore.fetchTemplates()"
        class="font-pixel text-[8px] text-neon-blue border border-neon-blue px-3 py-1 rounded hover:bg-neon-blue/10 transition-colors"
      >
        {{ t('hosts.retry') }}
      </button>
    </div>

    <!-- Template grid -->
    <div v-else class="grid grid-cols-2 gap-4">
      <button
        v-for="template in hostStore.templates"
        :key="template.template_id"
        type="button"
        class="bg-dark-surface border-2 rounded-lg p-4 text-left transition-all focus:outline-none focus:ring-2 focus:ring-neon-purple/50"
        :class="
          selected === template.template_id
            ? 'border-neon-purple shadow-pixel'
            : 'border-dark-accent hover:border-neon-purple/50 hover:shadow-pixel'
        "
        @click="selectTemplate(template.template_id)"
        @keydown.enter="selectTemplate(template.template_id)"
      >
        <!-- Icon -->
        <div class="flex justify-center mb-2 text-neon-purple">
          <PixelIcon :name="template.icon" size="xl" />
        </div>

        <!-- Name -->
        <p class="font-pixel text-xs text-neon-blue text-center truncate">
          {{ template.name }}
        </p>

        <!-- Description -->
        <p class="text-[10px] text-gray-400 text-center mt-1 line-clamp-2">
          {{ template.description }}
        </p>

      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useHostStore } from '@/stores/hosts'
import PixelIcon from '@/components/ui/PixelIcon.vue'

const { t, locale } = useI18n()
const hostStore = useHostStore()
const selected = ref<string | null>(null)

const emit = defineEmits<{
  select: [templateId: string]
}>()

function selectTemplate(templateId: string) {
  selected.value = templateId
  emit('select', templateId)
}

onMounted(() => {
  hostStore.fetchTemplates(locale.value)
})
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
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
