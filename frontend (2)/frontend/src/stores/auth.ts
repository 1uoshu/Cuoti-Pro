import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api, request } from '../api'
import type { User } from '../types'

interface AuthResponse {
  user: User
  access_token: string
  token_type: string
}

const tokenKey = 'smart-learning-token'
const userKey = 'smart-learning-user'

function storedUser(): User | null {
  const raw = localStorage.getItem(userKey)
  if (!raw) return null
  try {
    return JSON.parse(raw) as User
  } catch {
    localStorage.removeItem(userKey)
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(tokenKey) || '')
  const user = ref<User | null>(storedUser())
  const isAuthenticated = computed(() => Boolean(token.value))

  function setSession(payload: AuthResponse) {
    token.value = payload.access_token
    user.value = payload.user
    localStorage.setItem(tokenKey, payload.access_token)
    localStorage.setItem(userKey, JSON.stringify(payload.user))
  }

  function clearSession() {
    token.value = ''
    user.value = null
    localStorage.removeItem(tokenKey)
    localStorage.removeItem(userKey)
  }

  async function login(username: string, password: string) {
    const payload = await request<AuthResponse>(api.post('/auth/login', { username, password }))
    setSession(payload)
  }

  async function register(payload: { username: string; password: string; nickname: string; grade?: string; main_subject?: string }) {
    const result = await request<AuthResponse>(api.post('/auth/register', payload))
    setSession(result)
  }

  async function refreshProfile() {
    user.value = await request<User>(api.get('/auth/me'))
    localStorage.setItem(userKey, JSON.stringify(user.value))
  }

  async function logout() {
    try {
      await request(api.post('/auth/logout'))
    } finally {
      clearSession()
    }
  }

  return { token, user, isAuthenticated, login, register, refreshProfile, logout, clearSession }
})
