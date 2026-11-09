// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'

import AppearancePanel from '@/components/settings/AppearancePanel.vue'
import { useThemeStore } from '@/stores/theme'
import { themes } from '@/theme/themes'

/**
 * `stubActions: true`（默认）用来断言"点了哪个动作"；
 * `stubActions: false` 用来验证真实行为（状态、落盘、DOM 主题）。
 */
const mountPanel = (stubActions: boolean) => {
  const pinia = createTestingPinia({ createSpy: vi.fn, stubActions })
  const store = useThemeStore(pinia)
  const wrapper = mount(AppearancePanel, { global: { plugins: [pinia] } })
  return { wrapper, store }
}

const otherTheme = (currentId: string) => themes.find((theme) => theme.id !== currentId)!

describe('AppearancePanel', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('列出全部已注册主题，并把当前主题标记为使用中', () => {
    const { wrapper } = mountPanel(true)

    expect(wrapper.findAll('.theme-card')).toHaveLength(themes.length)
    const badges = wrapper.findAll('.theme-card__badge')
    expect(badges).toHaveLength(1)
    expect(badges[0].text()).toBe('使用中')
  })

  it('点主题卡片调用 store 的 setTheme，而不是自己改状态', async () => {
    const { wrapper, store } = mountPanel(true)
    const target = otherTheme(store.themeId)
    const index = themes.indexOf(target)

    await wrapper.findAll('.theme-card')[index].trigger('click')

    expect(store.setTheme).toHaveBeenCalledWith(target.id)
  })

  it('真实切换主题：store 状态、document 主题标记与 localStorage 同步更新', async () => {
    const { wrapper, store } = mountPanel(false)
    const target = otherTheme(store.themeId)

    await wrapper.findAll('.theme-card')[themes.indexOf(target)].trigger('click')

    expect(store.themeId).toBe(target.id)
    expect(document.documentElement.dataset.theme).toBe(target.id)
    expect(JSON.parse(localStorage.getItem('my-agent.theme')!)).toMatchObject({
      themeId: target.id,
    })
  })

  it('切到深色后说明文字变成「深色」，document 的 colorScheme 跟着变', async () => {
    const { wrapper } = mountPanel(false)

    await wrapper.findAll('input[type="radio"]')[1].setValue(true)

    expect(wrapper.text()).toContain('深色')
    expect(document.documentElement.dataset.mode).toBe('dark')
    expect(document.documentElement.style.colorScheme).toBe('dark')
  })
})
