import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Session } from '@supabase/supabase-js'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import router from '@/router'
import { usePlayerStore } from '@/stores/player'

interface User {
  id: string
  email: string
  display_name: string | null
  avatar_url: string | null
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const session = ref<Session | null>(null)
  const loading = ref(true)
  const error = ref<string | null>(null)
  const isAdmin = ref(false)

  const isAuthenticated = computed(() => !!session.value)
  const accessToken = computed(() => session.value?.access_token ?? null)

  async function signInWithGoogle() {
    error.value = null
    try {
      const { error: signInError } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: window.location.origin + '/auth/callback',
        },
      })
      if (signInError) {
        error.value = signInError.message
        throw signInError
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Sign in failed'
      throw err
    }
  }

  async function signOut() {
    error.value = null
    try {
      usePlayerStore().stop()
      await supabase.auth.signOut()
      user.value = null
      session.value = null
      isAdmin.value = false
      router.push('/login')
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Sign out failed'
      throw err
    }
  }

  async function fetchAdminStatus() {
    try {
      const sess = await api.get<{ is_admin: boolean }>('/api/v1/auth/session')
      isAdmin.value = sess.is_admin
    } catch {
      isAdmin.value = false
    }
  }

  async function initialize() {
    loading.value = true
    error.value = null
    try {
      const { data } = await supabase.auth.getSession()
      session.value = data.session

      if (data.session?.user) {
        user.value = {
          id: data.session.user.id,
          email: data.session.user.email ?? '',
          display_name: data.session.user.user_metadata?.full_name ?? null,
          avatar_url: data.session.user.user_metadata?.avatar_url ?? null,
        }
        await fetchAdminStatus()
      }

      supabase.auth.onAuthStateChange(async (_event, newSession) => {
        session.value = newSession

        if (newSession?.user) {
          user.value = {
            id: newSession.user.id,
            email: newSession.user.email ?? '',
            display_name: newSession.user.user_metadata?.full_name ?? null,
            avatar_url: newSession.user.user_metadata?.avatar_url ?? null,
          }
          await fetchAdminStatus()
        } else {
          user.value = null
          isAdmin.value = false
        }
      })
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Initialization failed'
      console.error('Auth initialization failed:', err)
    } finally {
      loading.value = false
    }
  }

  return {
    user,
    session,
    loading,
    error,
    isAuthenticated,
    isAdmin,
    accessToken,
    signInWithGoogle,
    signOut,
    initialize,
  }
})
