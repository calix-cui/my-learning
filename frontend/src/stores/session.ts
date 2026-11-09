/**
 * 登录状态：全应用只有这一份。
 *
 * Pinia setup store 写法：state 用 ref、派生用 computed、动作就是普通函数。
 * 约定（vue-pinia-best-practices）：**所有 state 都必须在 return 里出现**，
 * 否则 devtools 与 SSR 拿不到；组件侧解构要用 storeToRefs，直接解构会丢响应性。
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  fetchMe,
  login as loginApi,
  logout as logoutApi,
  register as registerApi,
} from '@/api/auth'
import { onUnauthorized } from '@/api/unauthorized'
import type { AuthUser } from '@/types/api'

export const useSessionStore = defineStore('session', () => {
  const user = ref<AuthUser | null>(null)
  /** 是否已经问过后端一次（避免守卫每次跳转都请求 /auth/me） */
  const loaded = ref(false)

  const isLoggedIn = computed(() => user.value !== null)
  const displayName = computed(
    () => user.value?.display_name?.trim() || user.value?.email || '未登录',
  )
  const avatarText = computed(() => (displayName.value[0] ?? '?').toUpperCase())

  /** 首次进入应用时确认登录态；401 视为未登录，不抛错 */
  async function loadCurrentUser(): Promise<AuthUser | null> {
    try {
      user.value = await fetchMe()
    } catch {
      user.value = null
    } finally {
      loaded.value = true
    }
    return user.value
  }

  async function login(email: string, password: string): Promise<AuthUser> {
    user.value = await loginApi(email, password)
    loaded.value = true
    return user.value
  }

  async function register(
    email: string,
    password: string,
    displayNameInput?: string,
  ): Promise<AuthUser> {
    user.value = await registerApi(email, password, displayNameInput)
    loaded.value = true
    return user.value
  }

  async function logout(): Promise<void> {
    try {
      await logoutApi()
    } finally {
      // 后端失败也要清本地，否则界面会卡在「半登录」
      clear()
    }
  }

  /** 401 时清空本地状态（由 client 拦截器调用） */
  function clear(): void {
    user.value = null
    loaded.value = true
  }

  // 任何请求收到 401 都会走到这里：把本地登录态清掉，
  // 后续路由守卫看到未登录就会把人挡在登录页。
  onUnauthorized(clear)

  return {
    user,
    loaded,
    isLoggedIn,
    displayName,
    avatarText,
    loadCurrentUser,
    login,
    register,
    logout,
    clear,
  }
})
