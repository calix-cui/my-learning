// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useThemeStore } from './theme'

const appearance = {
  theme_id: null as string | null,
  theme_mode: null as 'light' | 'dark' | 'system' | null,
  update_time: null as string | null,
}

vi.mock('@/api/settings', () => ({
  fetchAppearance: vi.fn(() => Promise.resolve({ ...appearance })),
  saveAppearance: vi.fn((patch: Record<string, unknown>) => {
    Object.assign(appearance, patch)
    return Promise.resolve({ ...appearance })
  }),
}))

const { fetchAppearance, saveAppearance } = await import('@/api/settings')

function fakeStorage() {
  const map = new Map<string, string>()
  return {
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => void map.set(key, value),
    removeItem: (key: string) => void map.delete(key),
  }
}

describe('主题与账号同步', () => {
  beforeEach(() => {
    appearance.theme_id = null
    appearance.theme_mode = null
    vi.clearAllMocks()
    vi.stubGlobal('localStorage', fakeStorage())
    vi.stubGlobal('window', { matchMedia: () => ({ matches: false, addEventListener() {} }) })
    setActivePinia(createPinia())
  })

  it('账号没存过外观时，把本机偏好写上去', async () => {
    const store = useThemeStore()
    store.initTheme()

    await store.syncFromAccount()

    expect(fetchAppearance).toHaveBeenCalled()
    expect(saveAppearance).toHaveBeenCalledWith({ theme_id: 'pine', theme_mode: 'system' })
  })

  it('账号存过外观时以账号为准（并落盘到本机）', async () => {
    appearance.theme_id = 'sand'
    appearance.theme_mode = 'dark'
    const store = useThemeStore()
    store.initTheme()

    await store.syncFromAccount()

    expect(store.themeId).toBe('sand')
    expect(store.mode).toBe('dark')
    expect(localStorage.getItem('my-agent.theme')).toContain('sand')
  })

  it('账号里是未知主题 id 时保持本机不动', async () => {
    appearance.theme_id = 'not-a-theme'
    const store = useThemeStore()
    store.initTheme()

    await store.syncFromAccount()

    expect(store.themeId).toBe('pine')
  })

  it('切换主题会写回账号', async () => {
    const store = useThemeStore()
    store.initTheme()

    store.setTheme('indigo')
    await vi.waitFor(() => expect(saveAppearance).toHaveBeenCalled())

    expect(saveAppearance).toHaveBeenCalledWith({ theme_id: 'indigo', theme_mode: 'system' })
  })

  it('接口失败不影响本机切换', async () => {
    vi.mocked(saveAppearance).mockRejectedValueOnce(new Error('401'))
    const store = useThemeStore()
    store.initTheme()

    expect(() => store.setTheme('graphite')).not.toThrow()
    expect(store.themeId).toBe('graphite')
  })
})
