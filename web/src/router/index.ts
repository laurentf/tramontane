import { createRouter, createWebHistory } from 'vue-router'
import { watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import AppLayout from '@/layouts/AppLayout.vue'
import AuthLayout from '@/layouts/AuthLayout.vue'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    requiresAdmin?: boolean
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      component: AuthLayout,
      children: [
        {
          path: '',
          name: 'login',
          component: () => import('@/views/auth/LoginView.vue'),
        },
      ],
    },
    {
      path: '/auth/callback',
      component: AuthLayout,
      children: [
        {
          path: '',
          name: 'auth-callback',
          component: () => import('@/views/auth/CallbackView.vue'),
        },
      ],
    },
    {
      path: '/',
      component: AppLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
        },
        {
          path: '/hosts',
          name: 'hosts',
          component: () => import('@/views/hosts/HostListView.vue'),
        },
        {
          path: '/hosts/create',
          name: 'host-create',
          meta: { requiresAdmin: true },
          component: () => import('@/views/hosts/HostCreateView.vue'),
        },
        {
          path: '/hosts/:id',
          name: 'host-detail',
          component: () => import('@/views/hosts/HostDetailView.vue'),
          props: true,
        },
        {
          path: '/schedule',
          name: 'schedule',
          meta: { requiresAdmin: true },
          component: () => import('@/views/schedule/ScheduleView.vue'),
        },
        {
          path: '/settings',
          name: 'settings',
          meta: { requiresAdmin: true },
          component: () => import('@/views/settings/SettingsView.vue'),
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()

  if (authStore.loading) {
    await new Promise<void>((resolve) => {
      const unwatch = watch(
        () => authStore.loading,
        (isLoading) => {
          if (!isLoading) {
            unwatch()
            resolve()
          }
        },
        { immediate: true }
      )
    })
  }

  if (authStore.isAuthenticated && to.path === '/login') {
    return { path: '/' }
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    return { path: '/' }
  }

  return true
})

export default router
