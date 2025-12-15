/**
 * 认证 Store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import type { User, LoginRequest, RegisterRequest } from '@/types/user'
import router from '@/router'
import { useChatStore } from '@/stores/chat'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(localStorage.getItem('token'))

  const isAuthenticated = computed(() => !!token.value && !!user.value)

  /**
   * 登录
   */
  async function login(credentials: LoginRequest): Promise<void> {
    const response = await authApi.login(credentials)
    
    if (response.success && response.token && response.user) {
      token.value = response.token
      user.value = response.user
      localStorage.setItem('token', response.token)
      // 登录成功后，清空上一用户的会话数据并拉取当前用户最近会话
      const chatStore = useChatStore()
      chatStore.resetState()
      await chatStore.loadLatestSession()
      
      // 跳转到首页
      router.push('/')
    } else {
      throw new Error(response.message || '登录失败')
    }
  }

  /**
   * 注册
   */
  async function register(data: RegisterRequest): Promise<void> {
    const response = await authApi.register(data)
    
    if (response.success && response.token && response.user) {
      token.value = response.token
      user.value = response.user
      localStorage.setItem('token', response.token)
      // 注册后同样刷新会话数据，避免复用旧状态
      const chatStore = useChatStore()
      chatStore.resetState()
      await chatStore.loadLatestSession()
      
      // 跳转到首页
      router.push('/')
    } else {
      throw new Error(response.message || '注册失败')
    }
  }

  /**
   * 登出
   */
  async function logout(): Promise<void> {
    await authApi.logout()
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    // 清空会话状态，防止串用上一用户的数据
    const chatStore = useChatStore()
    chatStore.resetState()
    
    // 跳转到登录页
    router.push('/login')
  }

  /**
   * 获取当前用户信息
   */
  async function fetchCurrentUser(): Promise<void> {
    try {
      const currentUser = await authApi.getCurrentUser()
      user.value = currentUser
    } catch (error) {
      // 如果获取失败，清除 token
      token.value = null
      user.value = null
      localStorage.removeItem('token')
      throw error
    }
  }

  /**
   * 初始化：如果有 token，尝试获取用户信息
   */
  async function init(): Promise<void> {
    if (token.value) {
      try {
        await fetchCurrentUser()
      } catch (error) {
        // 静默失败，用户可能需要重新登录
        console.error('初始化用户信息失败:', error)
      }
    }
  }

  return {
    user,
    token,
    isAuthenticated,
    login,
    register,
    logout,
    fetchCurrentUser,
    init
  }
})
