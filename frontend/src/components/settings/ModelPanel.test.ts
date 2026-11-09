// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import ElementPlus from 'element-plus'
import { describe, expect, it, vi } from 'vitest'

import ModelPanel from './ModelPanel.vue'

async function mountPanel(model: Record<string, unknown> = {}) {
  const pinia = createTestingPinia({
    createSpy: vi.fn,
    stubActions: true,
    initialState: {
      settings: {
        loaded: true,
        model: {
          provider: 'openai',
          base_url: 'https://api.deepseek.com/v1',
          model: 'deepseek-chat',
          timeout_seconds: 30,
          has_api_key: true,
          api_key_hint: '4321',
          can_store_api_key: true,
          inherited_from_env: false,
          update_time: '2026-11-09 20:00:00',
          ...model,
        },
      },
    },
  })

  const wrapper = mount(ModelPanel, { global: { plugins: [pinia, ElementPlus] } })
  // onMounted 里 await 了 store.load()，要等微任务跑完表单才回填
  await flushPromises()
  return { wrapper, store: pinia }
}

describe('ModelPanel', () => {
  it('回填已保存的配置', async () => {
    const { wrapper } = await mountPanel()

    const inputs = wrapper.findAll('input')
    const values = inputs.map((input) => (input.element as HTMLInputElement).value)

    expect(values).toContain('https://api.deepseek.com/v1')
    expect(values).toContain('deepseek-chat')
  })

  it('Key 只显示掩码与末四位', async () => {
    const { wrapper } = await mountPanel()

    // el-input 把值渲染在 input.value 上，不在文本节点里
    const values = wrapper
      .findAll('input')
      .map((input) => (input.element as HTMLInputElement).value)

    expect(values.some((value) => value.endsWith('4321') && value.includes('•'))).toBe(true)
    expect(values.join('')).not.toContain('sk-')
  })

  it('继承环境变量时给出提示', async () => {
    const { wrapper } = await mountPanel({ inherited_from_env: true, has_api_key: true })

    expect(wrapper.text()).toContain('环境变量')
  })

  it('选内置演示时不显示 Base URL 字段', async () => {
    const { wrapper } = await mountPanel()

    await wrapper.findAll('.model__seg-item')[1].trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('Base URL')
  })
})
