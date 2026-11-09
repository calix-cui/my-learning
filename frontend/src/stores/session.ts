/**
 * 登录状态：全应用只有这一份。
 *
 * 不引 Pinia——只有一个用户对象，用模块级 reactive 足够，
 * 也避免为登录态再引入一套状态管理约定。
 */

import { reactive } from 'vue'

import {
  fetchMe,
  login as loginApi,
  logout as logoutApi,
  register as registerApi,
} from '@/api/auth'
import { onUnauthorized } from '@/api/unauthorized'
import type { AuthUser } from '@/types/api'

interface SessionState {
  user: AuthUser | null
  /** 是否已经问过后端一次（避免守卫每次跳转都请求 /auth/me） */
  loaded: boolean
}

export const session = reactive<SessionState>({ user: null, loaded: false })

export function isLoggedIn(): boolean {
  return session.user !== null
}

/** 首次进入应用时确认登录态；401 视为未登录，不抛错 */
export async function loadCurrentUser(): Promise<AuthUser | null> {
  try {
    session.user = await fetchMe()
  } catch {
    session.user = null
  } finally {
    session.loaded = true
  }
  return session.user
}

export async function login(email: string, password: string): Promise<AuthUser> {
  session.user = await loginApi(email, password)
  session.loaded = true
  return session.user
}

export async function register(
  email: string,
  password: string,
  displayName?: string,
): Promise<AuthUser> {
  session.user = await registerApi(email, password, displayName)
  session.loaded = true
  return session.user
}

export async function logout(): Promise<void> {
  try {
    await logoutApi()
  } finally {
    // 后端失败也要清本地，否则界面会卡在「半登录」
    session.user = null
    session.loaded = true
  }
}

/** 401 时清空本地状态（由 client 拦截器调用） */
export function clearSession(): void {
  session.user = null
  session.loaded = true
}

// 任何请求收到 401 都会走到这里：把本地登录态清掉，
// 后续路由守卫看到未登录就会把人挡在登录页。
onUnauthorized(clearSession)
