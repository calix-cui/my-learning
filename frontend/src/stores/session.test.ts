import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

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

import { useSessionStore } from './session'

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
    setActivePinia(createPinia())
    fetchMe.mockReset()
    loginApi.mockReset()
    registerApi.mockReset()
    logoutApi.mockReset()
  })

  it('loadCurrentUser 成功时写入用户并标记 loaded', async () => {
    fetchMe.mockResolvedValue(alice)
    const store = useSessionStore()

    await expect(store.loadCurrentUser()).resolves.toEqual(alice)

    expect(store.user).toEqual(alice)
    expect(store.loaded).toBe(true)
    expect(store.isLoggedIn).toBe(true)
    expect(store.displayName).toBe('Alice')
  })

  it('loadCurrentUser 遇到 401 时静默视为未登录', async () => {
    fetchMe.mockRejectedValue(new Error('请先登录'))
    const store = useSessionStore()

    await expect(store.loadCurrentUser()).resolves.toBeNull()

    expect(store.user).toBeNull()
    expect(store.loaded).toBe(true)
    expect(store.isLoggedIn).toBe(false)
  })

  it('login/register 都会把用户写进 store', async () => {
    const store = useSessionStore()

    loginApi.mockResolvedValue(alice)
    await store.login('alice@example.com', 'password123')
    expect(store.user).toEqual(alice)

    store.clear()
    const bob = { ...alice, id: 2, email: 'bob@example.com' }
    registerApi.mockResolvedValue(bob)
    await store.register('bob@example.com', 'password123')
    expect(store.user).toEqual(bob)
    expect(registerApi).toHaveBeenCalledWith('bob@example.com', 'password123', undefined)
  })

  it('logout 即使后端失败也要清掉本地状态', async () => {
    const store = useSessionStore()
    store.user = alice
    logoutApi.mockRejectedValue(new Error('网络异常'))

    await expect(store.logout()).rejects.toThrow('网络异常')

    expect(store.user).toBeNull()
  })
})
