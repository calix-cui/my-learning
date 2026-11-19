import { ref } from 'vue'
import { defineStore } from 'pinia'
import { rescanSkills } from '@/api/skills'
import type { LocalSkill } from '@/types/api'

/** 账号目录只在认证初始化及设置页扫描，切换会话使用当前快照。 */
export const useSkillsStore = defineStore('skills', () => {
  const items = ref<LocalSkill[]>([])
  const version = ref('')
  const loading = ref(false)
  const error = ref('')
  const accountId = ref<number | null>(null)
  let generation = 0
  let inFlight: Promise<void> | null = null

  function reset() {
    generation++
    accountId.value = null
    items.value = []
    version.value = ''
    loading.value = false
    error.value = ''
    inFlight = null
  }

  function scan(): Promise<void> {
    if (inFlight) return inFlight
    if (accountId.value === null) return Promise.resolve()
    const requestGeneration = generation
    loading.value = true
    error.value = ''
    inFlight = rescanSkills()
      .then((data) => {
        if (requestGeneration !== generation) return
        items.value = data.items
        version.value = data.version
      })
      .catch((reason) => {
        if (requestGeneration !== generation) return
        error.value = reason instanceof Error ? reason.message : '读取 Skill 目录失败'
      })
      .finally(() => {
        if (requestGeneration === generation) {
          loading.value = false
          inFlight = null
        }
      })
    return inFlight
  }

  function initialize(id: number | null): Promise<void> {
    if (id === accountId.value) return inFlight ?? Promise.resolve()
    reset()
    accountId.value = id
    return scan()
  }

  return { items, version, loading, error, accountId, initialize, scan, reset }
})
