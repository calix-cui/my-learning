import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { rescanSkills } from '@/api/skills'
import { useSkillsStore } from './skills'
import type { SkillCatalog } from '@/types/api'

vi.mock('@/api/skills', () => ({ rescanSkills: vi.fn() }))
beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(rescanSkills).mockReset()
})
const result = (name = '指引'): SkillCatalog => ({
  items: [
    {
      key: 'user:guide',
      name,
      slug: 'guide',
      description: '用途',
      source: 'local',
      version: 'v1',
      trust: 'untrusted',
      tools: [],
      icon: 'sparkle',
    },
  ],
  version: name,
})

it('登录后只初始化一次，并发扫描合并，重新进入应用重新获取', async () => {
  let resolve!: (data: SkillCatalog) => void
  vi.mocked(rescanSkills).mockImplementationOnce(
    () =>
      new Promise((done) => {
        resolve = done
      }),
  )
  const skills = useSkillsStore()
  const initial = skills.initialize(1)
  const duplicate = skills.initialize(1)
  const settings = skills.scan()
  expect(rescanSkills).toHaveBeenCalledTimes(1)
  resolve(result())
  await Promise.all([initial, duplicate, settings])
  await skills.initialize(1)
  expect(rescanSkills).toHaveBeenCalledTimes(1)
  expect(skills.items[0].name).toBe('指引')
  setActivePinia(createPinia())
  vi.mocked(rescanSkills).mockResolvedValueOnce(result('刷新'))
  await useSkillsStore().initialize(1)
  expect(rescanSkills).toHaveBeenCalledTimes(2)
})

it('切换账号和退出时清理目录，旧账号迟到的响应不覆盖新账号', async () => {
  let resolveOld!: (data: SkillCatalog) => void
  vi.mocked(rescanSkills).mockImplementationOnce(
    () =>
      new Promise((done) => {
        resolveOld = done
      }),
  )
  const skills = useSkillsStore()
  const old = skills.initialize(1)
  vi.mocked(rescanSkills).mockResolvedValueOnce(result('新账号'))
  await skills.initialize(2)
  resolveOld(result('旧账号'))
  await old
  expect(skills.items[0].name).toBe('新账号')
  await skills.initialize(null)
  expect(skills.items).toEqual([])
  expect(skills.version).toBe('')
})

it('扫描失败保留上一次目录，并允许在设置中重试', async () => {
  vi.mocked(rescanSkills).mockResolvedValueOnce(result())
  const skills = useSkillsStore()
  await skills.initialize(1)
  vi.mocked(rescanSkills).mockRejectedValueOnce(new Error('读取失败'))
  await skills.scan()
  expect(skills.error).toBe('读取失败')
  expect(skills.items).toHaveLength(1)
  vi.mocked(rescanSkills).mockResolvedValueOnce(result('更新'))
  await skills.scan()
  expect(skills.error).toBe('')
  expect(skills.items[0].name).toBe('更新')
})
