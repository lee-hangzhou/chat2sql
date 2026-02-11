import { create } from 'zustand'
import * as authApi from '../api/auth'
import { clearTokens, getToken, setTokens } from '../api/client'
import type { UserInfo } from '../types'

interface AuthState {
  user: UserInfo | null
  isAuthenticated: boolean
  loading: boolean

  login: (username: string, password: string) => Promise<void>
  register: (username: string, email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  /** 页面初始化时从 token 恢复会话 */
  restore: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  loading: true,

  login: async (username, password) => {
    const res = await authApi.login({ username, password })
    setTokens(res.access_token, res.refresh_token)
    const user = await authApi.fetchCurrentUser()
    set({ user, isAuthenticated: true })
  },

  register: async (username, email, password) => {
    await authApi.register({ username, email, password })
  },

  logout: async () => {
    try {
      await authApi.logout()
    } finally {
      clearTokens()
      set({ user: null, isAuthenticated: false })
    }
  },

  restore: async () => {
    const token = getToken()
    if (!token) {
      set({ loading: false })
      return
    }
    try {
      const user = await authApi.fetchCurrentUser()
      set({ user, isAuthenticated: true, loading: false })
    } catch {
      clearTokens()
      set({ user: null, isAuthenticated: false, loading: false })
    }
  },
}))
