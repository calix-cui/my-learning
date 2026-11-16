// @vitest-environment happy-dom
import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatComposer from './ChatComposer.vue'
import AgentTimeline from './AgentTimeline.vue'
import type { AgentStep } from '@/types/api'

it('自动选择仅在深度回答可见，发送时锁定模式开关', async () => {
  const wrapper = mount(ChatComposer, {
    props: {
      modelValue: '问题',
      sending: false,
      disabled: false,
      maxLength: 4000,
      agentMode: false,
      autoSkills: false,
    },
    global: { stubs: { AppIcon: true, 'el-button': true } },
  })
  expect(wrapper.findAll('button')).toHaveLength(1)
  await wrapper.setProps({ agentMode: true })
  const auto = wrapper.findAll('button')[1]
  await auto.trigger('click')
  expect(wrapper.emitted('toggle-auto-skills')).toHaveLength(1)
  await wrapper.setProps({ autoSkills: true, sending: true })
  expect(auto.attributes('aria-pressed')).toBe('true')
  for (const button of wrapper.findAll('button')) expect(button.element.disabled).toBe(true)
  await auto.trigger('click')
  expect(wrapper.emitted('toggle-auto-skills')).toHaveLength(1)
  wrapper.unmount()
})

it('时间线展示技能名称和失败原因，不暴露控制函数或版本哈希', () => {
  const base: AgentStep = {
    seq: 1,
    kind: 'skill_loaded',
    content: null,
    tool_name: '__runtime_request_skill_load',
    tool_args: null,
    skill_key: 'builtin:meeting',
    skill_name: '会议纪要',
    skill_source: 'builtin',
    skill_version: 'private-version-hash',
    ok: null,
    duration_ms: null,
    create_time: '',
  }
  const wrapper = mount(AgentTimeline, {
    props: {
      running: false,
      steps: [
        base,
        { ...base, seq: 2, kind: 'skill_load_failed', content: '技能已更新，请重新发起任务' },
        {
          ...base,
          seq: 3,
          kind: 'skill_resource',
          ok: true,
          content: '已读取参考资料：references/checklist.md',
        },
        { ...base, seq: 4, kind: 'skill_resource', ok: false, content: '资源超过大小限制' },
      ],
    },
  })
  expect(wrapper.text()).toContain('已采用技能')
  expect(wrapper.text()).toContain('会议纪要')
  expect(wrapper.text()).toContain('内置技能')
  expect(wrapper.text()).toContain('技能已更新，请重新发起任务')
  expect(wrapper.text()).toContain('已读取参考资料')
  expect(wrapper.text()).toContain('参考资料未读取')
  expect(wrapper.text()).toContain('资源超过大小限制')
  expect(wrapper.text()).not.toContain('private-version-hash')
  expect(wrapper.text()).not.toContain('__runtime_request_skill_load')
  wrapper.unmount()
})
