// @vitest-environment happy-dom
import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatComposer from './ChatComposer.vue'
import AgentTimeline from './AgentTimeline.vue'
import type { AgentStep } from '@/types/api'

it('自动选择独立于深度回答，发送时锁定模式开关', async () => {
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
  expect(wrapper.get('button').text()).toContain('自动选择 Skill')
  await wrapper.setProps({ supportsReasoning: true })
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
  expect(wrapper.get('details.timeline').attributes('open')).toBeUndefined()
  expect(wrapper.findAll('.timeline__entry')).toHaveLength(4)
  expect(wrapper.text()).toContain('已加载 Skill')
  expect(wrapper.text()).toContain('会议纪要')
  expect(wrapper.text()).toContain('内置 Skill')
  expect(wrapper.text()).toContain('技能已更新，请重新发起任务')
  expect(wrapper.text()).toContain('已读取参考资料')
  expect(wrapper.text()).toContain('参考资料未读取')
  expect(wrapper.text()).toContain('资源超过大小限制')
  expect(wrapper.text()).not.toContain('private-version-hash')
  expect(wrapper.text()).not.toContain('__runtime_request_skill_load')
  wrapper.unmount()
})

it('工具和结果合并为一条可展开记录，普通思考只显示跳动省略号', async () => {
  const step: AgentStep = {
    seq: 1,
    kind: 'assistant_text',
    content: '中间说明',
    tool_name: null,
    tool_args: null,
    skill_key: null,
    skill_name: null,
    skill_source: null,
    skill_version: null,
    ok: null,
    duration_ms: null,
    create_time: '',
  }
  const wrapper = mount(AgentTimeline, { props: { running: true, steps: [step] } })
  expect(wrapper.get('[role="status"]').text()).toBe('正在思考...')
  expect(wrapper.findAll('.timeline__dots > span')).toHaveLength(3)
  expect(wrapper.find('summary').exists()).toBe(false)

  const call = {
    ...step,
    seq: 2,
    kind: 'tool_call',
    tool_name: 'calculator',
    tool_args: { expression: '3^5' },
  }
  await wrapper.setProps({ steps: [step, call] })
  const summary = wrapper.get('details.timeline > summary')
  expect(summary.text()).toContain('正在思考...')
  expect(wrapper.get('.timeline__entry > summary').text()).toContain('调用了工具 calculator')
  expect(wrapper.get('.timeline__entry .timeline__text').text()).toBe('等待执行结果')

  await wrapper.setProps({
    running: false,
    steps: [step, call, { ...call, seq: 3, kind: 'tool_result', content: '243', ok: true }],
  })
  expect(summary.text()).toContain('执行过程')
  expect(wrapper.findAll('.timeline__entry')).toHaveLength(1)
  const row = wrapper.get('.timeline__entry')
  expect(row.attributes('open')).toBeUndefined()
  expect(row.get('pre').text()).toContain('3^5')
  expect(row.get('.timeline__text').text()).toBe('243')
  await wrapper.setProps({ steps: [step] })
  expect(wrapper.find('.timeline').exists()).toBe(false)
  wrapper.unmount()
})

it('运行中同一个位置变成停止按钮，点一下交给上层终止', async () => {
  const wrapper = mount(ChatComposer, {
    props: {
      modelValue: '',
      sending: true,
      running: true,
      disabled: true,
      maxLength: 4000,
      agentMode: false,
      autoSkills: false,
    },
    global: { stubs: { AppIcon: true, 'el-button': true } },
  })
  expect(wrapper.find('[aria-label="发送"]').exists()).toBe(false)
  await wrapper.get('[aria-label="停止"]').trigger('click')
  expect(wrapper.emitted('stop')).toHaveLength(1)
  wrapper.unmount()
})
