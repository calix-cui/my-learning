// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ThemeCard from '@/components/theme/ThemeCard.vue'
import { pineTheme } from '@/theme/themes/pine'

const mountCard = (active: boolean, mode: 'light' | 'dark' = 'light') =>
  mount(ThemeCard, { props: { theme: pineTheme, active, mode } })

describe('ThemeCard', () => {
  it('渲染名称、说明与四个色块', () => {
    const wrapper = mountCard(false)

    expect(wrapper.text()).toContain(pineTheme.name)
    expect(wrapper.text()).toContain(pineTheme.description)
    expect(wrapper.findAll('.theme-card__swatches i')).toHaveLength(4)
  })

  it('色块取当前模式的配色，深色下不出现浅色块', () => {
    const light = mountCard(false, 'light').findAll('.theme-card__swatches i')[0]
    const dark = mountCard(false, 'dark').findAll('.theme-card__swatches i')[0]

    expect(light.attributes('style')).toContain(pineTheme.light.canvas)
    expect(dark.attributes('style')).toContain(pineTheme.dark.canvas)
  })

  it('选中态同时反映在 aria-pressed 与「使用中」徽标上', () => {
    expect(mountCard(false).attributes('aria-pressed')).toBe('false')
    expect(mountCard(false).find('.theme-card__badge').exists()).toBe(false)

    const active = mountCard(true, 'dark')
    expect(active.attributes('aria-pressed')).toBe('true')
    expect(active.find('.theme-card__badge').text()).toBe('使用中')
    expect(active.classes()).toContain('is-active')
  })

  it('点击后把主题 id 交给父组件（组件自己不切换）', async () => {
    const wrapper = mountCard(false)

    await wrapper.trigger('click')

    expect(wrapper.emitted('select')).toEqual([[pineTheme.id]])
    expect(wrapper.classes()).not.toContain('is-active')
  })
})
