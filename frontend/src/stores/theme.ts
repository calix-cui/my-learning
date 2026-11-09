import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { applyThemeToDocument, COLOR_KEYS } from '@/theme/apply'
import { defaultThemeId, findTheme } from '@/theme/themes'
import type { ThemeColors, ThemeDefinition, ThemeMode, ThemeModeSetting } from '@/theme/types'

const STORAGE_KEY = 'my-agent.theme'

interface PersistedTheme {
  themeId: string
  mode: ThemeModeSetting
}

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

function mediaQuery(): MediaQueryList | null {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return null
  return window.matchMedia('(prefers-color-scheme: dark)')
}

export const useThemeStore = defineStore('theme', () => {
  const themeId = ref(defaultThemeId)
  const mode = ref<ThemeModeSetting>('system')
  /** 系统是否偏好暗色，只由 matchMedia 更新 */
  const systemDark = ref(false)
  const ready = ref(false)

  const currentTheme = computed<ThemeDefinition>(() => findTheme(themeId.value))
  /** 当前生效的明暗模式（把 system 解析成具体值） */
  const resolvedMode = computed<ThemeMode>(() =>
    mode.value === 'system' ? (systemDark.value ? 'dark' : 'light') : mode.value,
  )
  const currentColors = computed<ThemeColors>(() =>
    resolvedMode.value === 'dark' ? currentTheme.value.dark : currentTheme.value.light,
  )

  function persist(): void {
    const payload: PersistedTheme = { themeId: themeId.value, mode: mode.value }
    safeStorage()?.setItem(STORAGE_KEY, JSON.stringify(payload))
  }

  function paint(): void {
    applyThemeToDocument(currentTheme.value, resolvedMode.value)
  }

  /** 应用启动时调用一次：读本地设置 → 跟随系统 → 首次绘制前写进 DOM */
  function initTheme(): void {
    if (ready.value) return

    const persisted = readPersisted()
    const query = mediaQuery()

    if (persisted) {
      themeId.value = findTheme(persisted.themeId).id
      mode.value = persisted.mode
    }

    if (query) {
      systemDark.value = query.matches
      query.addEventListener('change', (event) => {
        systemDark.value = event.matches
        if (mode.value === 'system') paint()
      })
    }

    ready.value = true
    paint()
  }

  function setTheme(nextThemeId: string): void {
    themeId.value = findTheme(nextThemeId).id
    persist()
    paint()
  }

  function setMode(nextMode: ThemeModeSetting): void {
    mode.value = nextMode
    persist()
    paint()
  }

  return {
    // state
    themeId,
    mode,
    systemDark,
    ready,
    // getters
    currentTheme,
    resolvedMode,
    currentColors,
    // actions
    initTheme,
    setTheme,
    setMode,
  }
})

/**
 * 校验一套颜色是否给全：新增主题时若漏字段，这里会直接报出来，
 * 而不是等界面上出现空白区域再排查。
 */
export function missingColorKeys(colors: ThemeColors): string[] {
  return COLOR_KEYS.filter((key) => !colors[key])
}
