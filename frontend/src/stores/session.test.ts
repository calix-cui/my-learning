import { beforeEach, describe, expect, it, vi } from 'vitest'

const { fetchMe, loginApi, registerApi, logoutApi } = vi.hoisted(() => ({
  fetchMe: vi.fn(),
  loginApi: vi.fn(),
  registerApi: vi.fn(),
  logoutApi: vi.fn(),
}))

vi.mock('@/api/auth', () => ({
  fetchMe,
  login: loginApi,
  register: registerApi,
  logout: logoutApi,
}))

import {
  clearSession,
  isLoggedIn,
  loadCurrentUser,
  login,
  logout,
  register,
  session,
} from './session'

const alice = {
  id: 1,
  email: 'alice@example.com',
  display_name: 'Alice',
  role: 'user',
  is_active: true,
  create_time: '2026-11-09 10:00:00',
  last_login_time: null,
}

describe('stores/session', () => {
  beforeEach(() => {
    clearSession()
    session.loaded = false
    fetchMe.mockReset()
    loginApi.mockReset()
    registerApi.mockReset()
    logoutApi.mockReset()
  })

  it('loadCurrentUser 成功时写入用户并标记 loaded', async () => {
    fetchMe.mockResolvedValue(alice)

    await expect(loadCurrentUser()).resolves.toEqual(alice)

    expect(session.user).toEqual(alice)
    expect(session.loaded).toBe(true)
    expect(isLoggedIn()).toBe(true)
  })

  it('loadCurrentUser 遇到 401 时静默视为未登录', async () => {
    fetchMe.mockRejectedValue(new Error('请先登录'))

    await expect(loadCurrentUser()).resolves.toBeNull()

    expect(session.user).toBeNull()
    expect(session.loaded).toBe(true)
    expect(isLoggedIn()).toBe(false)
  })

  it('login/register 都会把用户写进 store', async () => {
    loginApi.mockResolvedValue(alice)
    await login('alice@example.com', 'password123')
    expect(session.user).toEqual(alice)

    clearSession()
    const bob = { ...alice, id: 2, email: 'bob@example.com' }
    registerApi.mockResolvedValue(bob)
    await register('bob@example.com', 'password123')
    expect(session.user).toEqual(bob)
    expect(registerApi).toHaveBeenCalledWith('bob@example.com', 'password123', undefined)
  })

  it('logout 即使后端失败也要清掉本地状态', async () => {
    session.user = alice
    logoutApi.mockRejectedValue(new Error('网络异常'))

    await expect(logout()).rejects.toThrow('网络异常')

    expect(session.user).toBeNull()
  })
})
