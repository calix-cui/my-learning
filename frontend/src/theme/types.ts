/**
 * 主题系统的类型定义。
 *
 * 一套「主题」= 一组语义色 + 元信息；同一主题必须同时给 light 与 dark 两套颜色，
 * 因此「新增主题」只需在 `themes/` 里加一个文件并注册，不必改组件。
 */

export type ThemeMode = 'light' | 'dark'
export type ThemeModeSetting = ThemeMode | 'system'

/** 语义色 token：组件只允许用这些名字，不允许写死十六进制值 */
export interface ThemeColors {
  /** 页面底色 */
  canvas: string
  /** 卡片、输入框、浮层底色 */
  surface: string
  /** 侧栏、代码块、分组背景 */
  sunken: string
  /** 正文 */
  ink: string
  /** 次要文字 */
  muted: string
  /** 装饰性文字（禁用态、分隔符） */
  faint: string
  line: string
  lineStrong: string
  /** 唯一强调色：主按钮、选中态、用户气泡 */
  accent: string
  accentHover: string
  /** 强调色的浅色底 */
  accentSoft: string
  /** 强调色之上的文字色 */
  onAccent: string
  success: string
  successSoft: string
  warn: string
  warnSoft: string
  danger: string
  dangerSoft: string
}

export interface ThemeDefinition {
  /** 稳定 id，存进 localStorage，不要随文案改 */
  id: string
  name: string
  description: string
  light: ThemeColors
  dark: ThemeColors
}

/** 与主题无关的排版/间距/圆角，全局只有一份 */
export interface StaticTokens {
  fontSans: string
  fontSerif: string
  fontMono: string
  radiusSm: string
  radiusMd: string
  radiusLg: string
  spaceXs: string
  spaceSm: string
  spaceMd: string
  spaceLg: string
  spaceXl: string
  sidebarWidth: string
  contentWidth: string
  readingWidth: string
}
