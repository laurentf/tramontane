<template>
  <svg
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    :class="sizeClass"
    class="inline-block"
    aria-hidden="true"
  >
    <path :d="iconPath" fill="currentColor" />
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  name: string
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
})

const icons: Record<string, string> = {
  home: 'M12 2L2 12h3v8h6v-6h2v6h6v-8h3L12 2zm0 3.5L18 11v7h-2v-6H8v6H6v-7l6-5.5z',
  user: 'M15 2H9v2H7v6h2V4h6V2zm0 8H9v2h6v-2zm0-6h2v6h-2V4zM4 16h2v-2h12v2H6v4h12v-4h2v6H4v-6z',
  chat: 'M20 2H2v20h2V4h16v12H6v2H4v2h2v-2h16V2h-2z',
  sliders: 'M17 4h2v10h-2V4zm0 12h-2v2h2v2h2v-2h2v-2h-4zm-4-6h-2v10h2V10zm-8 2H3v2h2v6h2v-6h2v-2H5zm8-8h-2v2H9v2h6V6h-2V4zM5 4h2v6H5V4z',
  heart: 'M9 2H5v2H3v2H1v6h2v2h2v2h2v2h2v2h2v2h2v-2h2v-2h2v-2h2v-2h2v-2h2V6h-2V4h-2V2h-4v2h-2v2h-2V4H9V2zm0 2v2h2v2h2V6h2V4h4v2h2v6h-2v2h-2v2h-2v2h-2v2h-2v-2H9v-2H7v-2H5v-2H3V6h2V4h4z',
  shield: 'M22 2H2v12h2V4h16v10h2V2zM6 14H4v2h2v-2zm0 2h2v2h2v2H8v-2H6v-2zm4 4v2h4v-2h2v-2h-2v2h-4zm10-6h-2v2h-2v2h2v-2h2v-2z',
  zap: 'M12 1h2v8h8v4h-2v-2h-8V5h-2V3h2V1zM8 7V5h2v2H8zM6 9V7h2v2H6zm-2 2V9h2v2H4zm10 8v2h-2v2h-2v-8H2v-4h2v2h8v6h2zm2-2v2h-2v-2h2zm2-2v2h-2v-2h2zm0 0h2v-2h-2v2z',
  briefcase: 'M8 3h8v4h6v14H2V7h6V3zm2 4h4V5h-4v2zM4 9v10h16V9H4z',
  'mood-happy': 'M5 3h14v2H5V3zm0 16H3V5h2v14zm14 0v2H5v-2h14zm0 0h2V5h-2v14zM10 8H8v2h2V8zm4 0h2v2h-2V8zm-5 6v-2H7v2h2zm6 0v2H9v-2h6zm0 0h2v-2h-2v2z',
  trash: 'M16 2v4h6v2h-2v14H4V8H2V6h6V2h8zm-2 2h-4v2h4V4zm0 4H6v12h12V8h-4zm-5 2h2v8H9v-8zm6 0h-2v8h2v-8z',
  flag: 'M3 2h10v2h8v14H11v-2H5v6H3V2zm2 12h8v2h6V6h-8V4H5v10z',
  'chevron-left': 'M16 5v2h-2V5h2zm-4 4V7h2v2h-2zm-2 2V9h2v2h-2zm0 2H8v-2h2v2zm2 2v-2h-2v2h2zm0 0h2v2h-2v-2zm4 4v-2h-2v2h2z',
  plus: 'M11 4h2v7h7v2h-7v7h-2v-7H4v-2h7V4z',
  'moon-stars': 'M20 0h2v2h2v2h-2v2h-2V4h-2V2h2V0ZM8 4h8v2h-2v2h-2V6H8V4ZM6 8V6h2v2H6Zm0 8H4V8h2v8Zm2 2H6v-2h2v2Zm8 0v2H8v-2h8Zm2-2v2h-2v-2h2Zm-2-4v-2h2V8h2v8h-2v-4h-2Zm-4 0h4v2h-4v-2Zm0 0V8h-2v4h2Zm-8 6H2v2H0v2h2v2h2v-2h2v-2H4v-2Z',
  loader: 'M13 2h-2v6h2V2zm0 14h-2v6h2v-6zm9-5v2h-6v-2h6zM8 13v-2H2v2h6zm7-6h2v2h-2V7zm4-2h-2v2h2V5zM9 7H7v2h2V7zM5 5h2v2H5V5zm10 12h2v2h2v-2h-2v-2h-2v2zm-8 0v-2h2v2H7v2H5v-2h2z',
  check: 'M18 6h2v2h-2V6zm-2 4V8h2v2h-2zm-2 2v-2h2v2h-2zm-2 2h2v-2h-2v2zm-2 2h2v-2h-2v2zm-2 0v2h2v-2H8zm-2-2h2v2H6v-2zm0 0H4v-2h2v2z',
  close: 'M5 5h2v2H5V5zm4 4H7V7h2v2zm2 2H9V9h2v2zm2 0h-2v2H9v2H7v2H5v2h2v-2h2v-2h2v-2h2v2h2v2h2v2h2v-2h-2v-2h-2v-2h-2v-2zm2-2v2h-2V9h2zm2-2v2h-2V7h2zm0 0V5h2v2h-2z',
  alert: 'M13 1h-2v2H9v2H7v2H5v2H3v2H1v2h2v2h2v2h2v2h2v2h2v2h2v-2h2v-2h2v-2h2v-2h2v-2h2v-2h-2V9h-2V7h-2V5h-2V3h-2V1zm0 2v2h2v2h2v2h2v2h2v2h-2v2h-2v2h-2v2h-2v2h-2v-2H9v-2H7v-2H5v-2H3v-2h2V9h2V7h2V5h2V3h2zm0 4h-2v6h2V7zm0 8h-2v2h2v-2z',
  android: 'M3 7h2v12H3V7zm16 0h2v12h-2V7zM7 5h10v2H7V5zm0 16h10v-2H7v2zm0-2h2V7h6v12h2V7h-2V5H9v2H7v12zm2-8h2v2H9v-2zm4 0h2v2h-2v-2zM9 3h2V1h2v2h2V1h-2V0h-2v1H9v2z',
  human: 'M10 2h4v4h-4V2zM3 7h18v2h-6v13h-2v-6h-2v6H9V9H3V7z',
  'human-handsup': 'M10 2h4v4h-4V2zM7 7h10v2h-2v13h-2v-6h-2v6H9V9H7V7zM5 5v2h2V5H5zm0 0H3V3h2v2zm14 0v2h-2V5h2zm0 0V3h2v2h-2z',
  'human-handsdown': 'M10 2h4v4h-4V2zM7 7h10v2h-2v13h-2v-6h-2v6H9V9H7V7zm-2 4h2V9H5v2zm0 0v2H3v-2h2zm14 0h-2V9h2v2zm0 0h2v2h-2v-2z',
  sword: 'M11 2h2v8h-2V2zM8 10h8v2H8v-2zm3 2h2v5h-2v-5zm-1 5h4v2h-4v-2z',
  capitol: 'M11 2h2v2h-2V2zM9 4h6v2H9V4zM7 6h10v2H7V6zM8 8h2v8H8V8zm3 0h2v8h-2V8zm3 0h2v8h-2V8zM6 16h12v2H6v-2z',
  refresh: 'M12 4V2h2v2h2v2h-2V4h-2zm-4 2h4V4H8v2zM6 8H4v2h2V8zm0 0h2V6H6v2zm12 0V6h-2v2h2zm0 0h2v8h-2V8zm-2 10v2h-2v-2h-2v-2h2v2h2zm-8 0h4v2H8v-2zm-2-2h2v2H6v-2zM4 8v8h2v-2H4V8z',
}

const iconPath = computed(() => icons[props.name] || '')

const sizeClass = computed(() => {
  const sizes: Record<string, string> = {
    xs: 'w-3 h-3',
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-6 h-6',
    xl: 'w-8 h-8',
  }
  return sizes[props.size]
})
</script>
