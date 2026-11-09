import { describe, expect, it } from 'vitest'

import { buildElementPlusVars, buildThemeVars, COLOR_KEYS } from '@/theme/apply'
import { findTheme, themes } from '@/theme/themes'

describe('theme tokens', () => {
  it('每个主题都给全了浅色与深色两套语义色', () => {
    for (const theme of themes) {
      for (const mode of ['light', 'dark'] as const) {
        const colors = theme[mode]
        for (const key of COLOR_KEYS) {
          expect(colors[key], `${theme.id}.${mode}.${key}`).toMatch(/^#[0-9a-f]{6}$/i)
        }
      }
    }
  })

  it('主题 id 唯一，且能找到默认主题', () => {
    const ids = themes.map((theme) => theme.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(findTheme('不存在的主题').id).toBe(themes[0].id)
  })

  it('编译出的 CSS 变量带模式标记与全部语义色', () => {
    const vars = buildThemeVars(findTheme('pine'), 'dark')
    expect(vars['--ma-mode']).toBe('dark')
    expect(vars['--ma-color-accent']).toBe(findTheme('pine').dark.accent)
    expect(Object.keys(vars)).toEqual(
      expect.arrayContaining(['--ma-color-canvas', '--ma-radius-md']),
    )
  })

  it('Element Plus 主色跟随 accent，深色模式向黑派生色阶', () => {
    const light = buildElementPlusVars('light')
    const dark = buildElementPlusVars('dark')
    expect(light['--el-color-primary']).toBe('var(--ma-color-accent)')
    expect(light['--el-color-primary-light-3']).toContain('#ffffff')
    expect(dark['--el-color-primary-light-3']).toContain('#000000')
  })
})
