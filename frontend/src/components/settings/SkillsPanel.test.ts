// @vitest-environment happy-dom
import { expect, it, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import SkillsPanel from './SkillsPanel.vue'
import { useSessionStore } from '@/stores/session'
import { useSkillsStore } from '@/stores/skills'
import { rescanSkills, getSkill } from '@/api/skills'

vi.mock('@/api/skills', () => ({
  rescanSkills: vi.fn(),
  getSkill: vi.fn(),
  exportLegacySkills: vi.fn(),
}))
afterEach(() => vi.clearAllMocks())

it('进入设置再次扫描，页面只读，说明按需读取，重新扫描更新目录', async () => {
  const pinia = createPinia()
  const session = useSessionStore(pinia)
  session.user = { id: 1 } as NonNullable<typeof session.user>
  const catalog = {
    items: [
      {
        key: 'user:guide',
        slug: 'guide',
        name: '本地说明',
        description: '用于整理',
        source: 'local' as const,
        trust: 'untrusted',
        version: 'v1',
        tools: [],
        icon: 'sparkle',
      },
    ],
    version: 'catalog1',
    legacy_count: 1,
  }
  vi.mocked(rescanSkills).mockResolvedValue(catalog)
  await useSkillsStore(pinia).initialize(1)
  const wrapper = mount(SkillsPanel, { global: { plugins: [pinia] } })
  await flushPromises()
  expect(rescanSkills).toHaveBeenCalledTimes(2)
  expect(wrapper.find('form').exists()).toBe(false)
  expect(wrapper.findAll('input, textarea')).toHaveLength(0)
  expect(wrapper.text()).toContain('Skill')
  expect(wrapper.text()).toContain('导出旧 Skill')
  expect(wrapper.text()).not.toContain('编辑')
  expect(getSkill).not.toHaveBeenCalled()
  vi.mocked(getSkill).mockResolvedValueOnce({ instructions: '**只读内容**' })
  await wrapper
    .findAll('button')
    .find((button) => button.text() === '查看说明')!
    .trigger('click')
  await flushPromises()
  expect(getSkill).toHaveBeenCalledWith('user:guide', 'catalog1')
  expect(wrapper.get('strong').text()).toBe('只读内容')
  vi.mocked(rescanSkills).mockResolvedValueOnce({ ...catalog, items: [], version: 'catalog2' })
  await wrapper
    .findAll('button')
    .find((button) => button.text() === '重新扫描')!
    .trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('尚未发现 Skill')
  wrapper.unmount()
})
