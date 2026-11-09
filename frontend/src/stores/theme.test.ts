import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// 测试跑在 node 环境（无 DOM），这里补一个最小 localStorage 实现
const memory = new Map<string, string>()
const fakeStorage = {
  getItem: (key: string) => memory.get(key) ?? null,
  setItem: (key: string, value: string) => void memory.set(key, value),
  removeItem: (key: string) => void memory.delete(key),
  clear: () => memory.clear(),
}

beforeEach(() => {
  memory.clear()
  vi.unstubAllGlobals()
  vi.stubGlobal('localStorage', fakeStorage)
  // 每个用例一套全新的 pinia，避免 store 单例在用例间串状态
  setActivePinia(createPinia())
})

function stubMatchMedia(matches: boolean) {
  const query = {
    matches,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }
  // 生产代码用 window.matchMedia（SSR 下没有 window），所以这里连 window 一起 stub
  vi.stubGlobal('window', { matchMedia: vi.fn(() => query) })
}

describe('stores/theme', () => {
  it('没有本地设置时用默认主题 + 跟随系统', async () => {
    stubMatchMedia(false)
    const { useThemeStore } = await import('@/stores/theme')
    const store = useThemeStore()
    store.initTheme()

    expect(store.themeId).toBe(store.currentTheme.id)
    expect(store.mode).toBe('system')
    expect(store.resolvedMode).toBe('light')
  })

  it('跟随系统时，系统偏好深色就解析为 dark', async () => {
    stubMatchMedia(true)
    const { useThemeStore } = await import('@/stores/theme')
    const store = useThemeStore()
    store.initTheme()

    expect(store.resolvedMode).toBe('dark')
  })

  it('切换主题与模式会写进 localStorage', async () => {
    stubMatchMedia(false)
    const { useThemeStore } = await import('@/stores/theme')
    const store = useThemeStore()
    store.initTheme()

    store.setTheme('sand')
    store.setMode('dark')

    expect(JSON.parse(localStorage.getItem('my-agent.theme') ?? '{}')).toEqual({
      themeId: 'sand',
      mode: 'dark',
    })
    expect(store.currentTheme.id).toBe('sand')
    expect(store.resolvedMode).toBe('dark')
  })

  it('启动时读取本地设置，主题 id 不存在则回落默认', async () => {
    stubMatchMedia(false)
    localStorage.setItem(
      'my-agent.theme',
      JSON.stringify({ themeId: '已删除的主题', mode: 'light' }),
    )
    const { useThemeStore } = await import('@/stores/theme')
    const store = useThemeStore()
    store.initTheme()

    expect(store.themeId).toBe(store.currentTheme.id)
    expect(store.resolvedMode).toBe('light')
  })
})
