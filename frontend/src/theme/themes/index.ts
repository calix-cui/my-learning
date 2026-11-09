import type { ThemeDefinition } from '../types'
import { graphiteTheme } from './graphite'
import { indigoTheme } from './indigo'
import { pineTheme } from './pine'
import { sandTheme } from './sand'

/**
 * 主题注册表：**新增主题只需在 `themes/` 加一个文件，再 push 到这里**。
 * 顺序就是设置页里的展示顺序，第一个是默认主题。
 */
export const themes: ThemeDefinition[] = [pineTheme, sandTheme, indigoTheme, graphiteTheme]

export const defaultThemeId = themes[0].id

export function findTheme(id: string): ThemeDefinition {
  return themes.find((theme) => theme.id === id) ?? themes[0]
}
