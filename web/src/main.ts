import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import '@fontsource/press-start-2p'
import './assets/styles/main.css'
import App from './App.vue'
import router from './router'

// Import locale files
import en from './locales/en.json'
import fr from './locales/fr.json'
import es from './locales/es.json'

// Load saved locale from localStorage, default to 'fr' (French radio)
const savedLocale = localStorage.getItem('tramontane-locale') || 'fr'

const i18n = createI18n({
  legacy: false,
  locale: savedLocale,
  fallbackLocale: 'en',
  messages: {
    en,
    fr,
    es,
  },
})

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(router)
app.use(i18n)

app.mount('#app')
