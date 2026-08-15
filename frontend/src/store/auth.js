import { defineStore } from 'pinia'
import { authApi } from '../api'

// 认证状态：token 与用户信息持久化到 localStorage，刷新不掉线
export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('access_token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null'),
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    isAdmin: (s) => s.user?.role === 'admin',
    nickname: (s) => s.user?.nickname || s.user?.username || '',
  },
  actions: {
    setAuth(token, user) {
      this.token = token
      this.user = user
      localStorage.setItem('access_token', token)
      localStorage.setItem('user', JSON.stringify(user))
    },
    async login(username, password) {
      const data = await authApi.login({ username, password })
      this.setAuth(data.access_token, data.user)
      return data.user
    },
    async register(payload) {
      return authApi.register(payload)
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
    },
  },
})
