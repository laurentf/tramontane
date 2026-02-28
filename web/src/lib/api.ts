import { useAuthStore } from '@/stores/auth'

const API_BASE = import.meta.env.VITE_API_URL || ''

interface ApiFetchOptions extends RequestInit {
  skipAuth?: boolean
}

async function apiFetch<T = unknown>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { skipAuth = false, ...fetchOptions } = options

  const headers = new Headers(fetchOptions.headers)

  if (!skipAuth) {
    const authStore = useAuthStore()
    const token = authStore.accessToken
    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }
  }

  if (fetchOptions.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const url = `${API_BASE}${path}`
  const response = await fetch(url, {
    ...fetchOptions,
    headers,
  })

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`
    try {
      const errorBody = await response.json()
      errorMessage = errorBody.error || errorBody.detail || errorMessage
    } catch {
      // If response body is not JSON, use status text
    }
    throw new Error(errorMessage)
  }

  return response.json()
}

export const api = {
  get<T = unknown>(path: string, options: ApiFetchOptions = {}): Promise<T> {
    return apiFetch<T>(path, { ...options, method: 'GET' })
  },

  post<T = unknown>(path: string, body?: unknown, options: ApiFetchOptions = {}): Promise<T> {
    return apiFetch<T>(path, {
      ...options,
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    })
  },

  patch<T = unknown>(path: string, body?: unknown, options: ApiFetchOptions = {}): Promise<T> {
    return apiFetch<T>(path, {
      ...options,
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    })
  },

  delete<T = unknown>(path: string, options: ApiFetchOptions = {}): Promise<T> {
    return apiFetch<T>(path, { ...options, method: 'DELETE' })
  },
}
