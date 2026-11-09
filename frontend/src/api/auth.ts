import client from './client'

import type { ApiResponse, AuthUser, LoginSession } from '@/types/api'

/** 注册并直接登录（成功后浏览器会拿到 HttpOnly Cookie） */
export async function register(
  email: string,
  password: string,
  displayName?: string,
): Promise<AuthUser> {
  const { data } = await client.post<ApiResponse<AuthUser>>('/auth/register', {
    email,
    password,
    display_name: displayName || null,
  })
  return data.data
}

/** 登录 */
export async function login(email: string, password: string): Promise<AuthUser> {
  const { data } = await client.post<ApiResponse<AuthUser>>(
    '/auth/login',
    { email, password },
    { skipAuthRedirect: true },
  )
  return data.data
}

/** 登出：后端删会话并清 Cookie，重复调用不报错 */
export async function logout(): Promise<void> {
  await client.post<ApiResponse<null>>('/auth/logout')
}

/** 当前登录用户；未登录时后端返回 401 */
export async function fetchMe(): Promise<AuthUser> {
  // 启动时的登录态探测：401 是正常结果，由调用方处理，不要触发整页跳转
  const { data } = await client.get<ApiResponse<AuthUser>>('/auth/me', { skipAuthRedirect: true })
  return data.data
}

/** 我的登录设备 */
export async function listSessions(): Promise<LoginSession[]> {
  const { data } = await client.get<ApiResponse<{ items: LoginSession[] }>>('/auth/sessions')
  return data.data.items
}

/** 撤销某台设备 */
export async function revokeSession(id: number): Promise<void> {
  await client.delete<ApiResponse<null>>(`/auth/sessions/${id}`)
}

/** 修改密码（成功后其他设备会被踢下线） */
export async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  await client.post<ApiResponse<null>>('/auth/password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}
