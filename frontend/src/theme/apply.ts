import { staticTokens } from './tokens'
import type { ThemeColors, ThemeDefinition, ThemeMode } from './types'

/** 每个主题都必须给全的语义色，缺一个就会在界面上出现「透明洞」 */
export const COLOR_KEYS: (keyof ThemeColors)[] = [
  'canvas',
  'surface',
  'sunken',
  'ink',
  'muted',
  'faint',
  'line',
  'lineStrong',
  'accent',
  'accentHover',
  'accentSoft',
  'onAccent',
  'success',
  'successSoft',
  'warn',
  'warnSoft',
  'danger',
  'dangerSoft',
]

/** 语义色 → CSS 变量名（组件里只写 var(--ma-color-*)） */
function colorVarName(key: keyof ThemeColors): string {
  return `--ma-color-${key.replace(/[A-Z]/g, (char) => `-${char.toLowerCase()}`)}`
}

/**
 * 把一套主题 + 模式编译成扁平 CSS 变量表。
 * 纯函数，便于单测；不接触 DOM。
 */
export function buildThemeVars(theme: ThemeDefinition, mode: ThemeMode): Record<string, string> {
  const colors = mode === 'dark' ? theme.dark : theme.light
  const vars: Record<string, string> = {
    '--ma-mode': mode,
    '--ma-font-sans': staticTokens.fontSans,
    '--ma-font-mono': staticTokens.fontMono,
    '--ma-radius-sm': staticTokens.radiusSm,
    '--ma-radius-md': staticTokens.radiusMd,
    '--ma-radius-lg': staticTokens.radiusLg,
    '--ma-radius-xl': staticTokens.radiusXl,
    '--ma-space-xs': staticTokens.spaceXs,
    '--ma-space-sm': staticTokens.spaceSm,
    '--ma-space-md': staticTokens.spaceMd,
    '--ma-space-lg': staticTokens.spaceLg,
    '--ma-space-xl': staticTokens.spaceXl,
    '--ma-sidebar-width': staticTokens.sidebarWidth,
    '--ma-content-width': staticTokens.contentWidth,
    '--ma-reading-width': staticTokens.readingWidth,
    '--ma-motion-hover': staticTokens.motionHover,
  }

  for (const key of COLOR_KEYS) {
    vars[colorVarName(key)] = colors[key]
  }

  return vars
}

/**
 * 让 Element Plus 跟随主题：主色取 accent 并派生明暗档。
 * 用 color-mix 派生，避免为每个主题手写 6 个色阶。
 */
export function buildElementPlusVars(mode: ThemeMode): Record<string, string> {
  const toward = mode === 'dark' ? '#000000' : '#ffffff'
  const mix = (percent: number) =>
    `color-mix(in srgb, var(--ma-color-accent) ${percent}%, ${toward})`

  return {
    '--el-color-primary': 'var(--ma-color-accent)',
    '--el-color-primary-light-3': mix(70),
    '--el-color-primary-light-5': mix(50),
    '--el-color-primary-light-7': mix(30),
    '--el-color-primary-light-8': mix(20),
    '--el-color-primary-light-9': 'var(--ma-color-accent-soft)',
    '--el-color-primary-dark-2': 'var(--ma-color-accent-hover)',
    '--el-color-success': 'var(--ma-color-success)',
    '--el-color-warning': 'var(--ma-color-warn)',
    '--el-color-danger': 'var(--ma-color-danger)',
    '--el-color-error': 'var(--ma-color-danger)',
    '--el-bg-color': 'var(--ma-color-surface)',
    '--el-bg-color-page': 'var(--ma-color-canvas)',
    '--el-bg-color-overlay': 'var(--ma-color-surface)',
    '--el-text-color-primary': 'var(--ma-color-ink)',
    '--el-text-color-regular': 'var(--ma-color-ink)',
    '--el-text-color-secondary': 'var(--ma-color-muted)',
    '--el-text-color-placeholder': 'var(--ma-color-faint)',
    '--el-border-color': 'var(--ma-color-line)',
    '--el-border-color-light': 'var(--ma-color-line)',
    '--el-border-color-lighter': 'var(--ma-color-line)',
    '--el-border-color-extra-light': 'var(--ma-color-line)',
    '--el-fill-color-blank': 'var(--ma-color-surface)',
    '--el-fill-color-light': 'var(--ma-color-sunken)',
    '--el-fill-color-lighter': 'var(--ma-color-sunken)',
    '--el-mask-color': 'rgba(0, 0, 0, 0.4)',
  }
}

/**
 * 把主题写进 `<html>`：`data-theme` / `data-mode` 供纯 CSS 分支使用，
 * CSS 变量挂在 `:root` 上，颜色变化只改一层，不触发组件重渲染。
 */
export function applyThemeToDocument(theme: ThemeDefinition, mode: ThemeMode): void {
  if (typeof document === 'undefined') return

  const root = document.documentElement
  const vars = { ...buildThemeVars(theme, mode), ...buildElementPlusVars(mode) }

  for (const [name, value] of Object.entries(vars)) {
    root.style.setProperty(name, value)
  }

  root.dataset.theme = theme.id
  root.dataset.mode = mode
  root.style.colorScheme = mode
}
