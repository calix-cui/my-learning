// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ModeSwitch from '@/components/theme/ModeSwitch.vue'
import type { ThemeModeSetting } from '@/theme/types'

/** 用 onUpdate:modelValue 回写 props，模拟 v-model 的双向绑定 */
const mountSwitch = (initial: ThemeModeSetting) =>
  mount(ModeSwitch, {
    props: {
      modelValue: initial,
      'onUpdate:modelValue': (value: ThemeModeSetting) => wrapper.setProps({ modelValue: value }),
    },
  })

let wrapper: ReturnType<typeof mount>

describe('ModeSwitch', () => {
  it('三档选项按顺序渲染，并用原生 radio 表达互斥', () => {
    wrapper = mountSwitch('light')

    expect(wrapper.get('[role="group"]').attributes('aria-label')).toBe('明暗模式')
    const inputs = wrapper.findAll('input[type="radio"]')
    expect(inputs.map((input) => input.attributes('value'))).toEqual(['light', 'dark', 'system'])
    expect(inputs.every((input) => input.attributes('name') === 'theme-mode')).toBe(true)
  })

  it('当前值对应的选项被选中且高亮', () => {
    wrapper = mountSwitch('system')

    const checked = wrapper
      .findAll('input[type="radio"]')
      .filter((input) => (input.element as HTMLInputElement).checked)
    expect(checked).toHaveLength(1)
    expect(checked[0].attributes('value')).toBe('system')
    expect(wrapper.findAll('.mode-switch__item')[2].classes()).toContain('is-active')
  })

  it('选中另一档后通过 v-model 抛出更新，父组件回写后高亮跟着走', async () => {
    wrapper = mountSwitch('light')

    await wrapper.findAll('input[type="radio"]')[1].setValue(true)

    expect(wrapper.emitted('update:modelValue')).toEqual([['dark']])
    expect(wrapper.findAll('.mode-switch__item')[1].classes()).toContain('is-active')
    expect(wrapper.findAll('.mode-switch__item')[0].classes()).not.toContain('is-active')
  })
})
