import { computed, reactive, readonly } from 'vue'

import { applyThemeToDocument, COLOR_KEYS } from '@/theme/apply'
import { findTheme, themes } from '@/theme/themes'
import type { ThemeColors, ThemeDefinition, ThemeMode, ThemeModeSetting } from '@/theme/types'

const STORAGE_KEY = 'my-agent.theme'

interface PersistedTheme {
  themeId: string
  mode: ThemeModeSetting
}

interface ThemeState {
  themeId: string
  mode: ThemeModeSetting
  /** 系统是否偏好暗色，只由 matchMedia 更新 */
  systemDark: boolean
  ready: boolean
}

const state = reactive<ThemeState>({
  themeId: themes[0].id,
  mode: 'system',
  systemDark: false,
  ready: false,
})

function safeStorage(): Storage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    // 隐私模式或被策略禁止时不要炸掉整个应用
    return null
  }
}

function readPersisted(): PersistedTheme | null {
  const raw = safeStorage()?.getItem(STORAGE_KEY)
  if (!raw) return null

  try {
    const parsed = JSON.parse(raw) as Partial<PersistedTheme>
    if (typeof parsed.themeId !== 'string' || typeof parsed.mode !== 'string') return null
    if (!['light', 'dark', 'system'].includes(parsed.mode)) return null
    return { themeId: parsed.themeId, mode: parsed.mode as ThemeModeSetting }
  } catch {
    return null
  }
}

function persist(): void {
  const payload: PersistedTheme = { themeId: state.themeId, mode: state.mode }
  safeStorage()?.setItem(STORAGE_KEY, JSON.stringify(payload))
}

function mediaQuery(): MediaQueryList | null {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return null
  return window.matchMedia('(prefers-color-scheme: dark)')
}

/** 当前生效的明暗模式（把 system 解析成具体值） */
export const resolvedMode = computed<ThemeMode>(() =>
  state.mode === 'system' ? (state.systemDark ? 'dark' : 'light') : state.mode,
)

export const currentTheme = computed<ThemeDefinition>(() => findTheme(state.themeId))

export const currentColors = computed<ThemeColors>(() =>
  resolvedMode.value === 'dark' ? currentTheme.value.dark : currentTheme.value.light,
)

function paint(): void {
  applyThemeToDocument(currentTheme.value, resolvedMode.value)
}

function syncSystemDark(query: MediaQueryList | null): void {
  if (!query) return
  state.systemDark = query.matches
}

/** 应用启动时调用一次：读本地设置 → 跟随系统 → 首次绘制前写进 DOM */
export function initTheme(): void {
  if (state.ready) return

  const persisted = readPersisted()
  const query = mediaQuery()

  if (persisted) {
    state.themeId = findTheme(persisted.themeId).id
    state.mode = persisted.mode
  }

  syncSystemDark(query)
  query?.addEventListener('change', (event) => {
    state.systemDark = event.matches
    if (state.mode === 'system') paint()
  })

  state.ready = true
  paint()
}

export function setTheme(themeId: string): void {
  state.themeId = findTheme(themeId).id
  persist()
  paint()
}

export function setMode(mode: ThemeModeSetting): void {
  state.mode = mode
  persist()
  paint()
}

/**
 * 校验一套颜色是否给全：新增主题时若漏字段，这里会直接报出来，
 * 而不是等界面上出现空白区域再排查。
 */
export function missingColorKeys(colors: ThemeColors): string[] {
  return COLOR_KEYS.filter((key) => !colors[key])
}

/** 只读快照，组件里用 useTheme() 取值 */
export const themeState = readonly(state)

export function useTheme() {
  return {
    themes,
    state: themeState,
    resolvedMode,
    currentTheme,
    currentColors,
    setTheme,
    setMode,
  }
}
