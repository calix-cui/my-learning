/**
 * 模型设置：侧栏底部的「模型」标签与设置页共用同一份状态。
 *
 * 与 theme/session 一样用 Pinia setup store；只存真正会变的东西——
 * 主题列表那种静态配置不要放进来（storeToRefs 只转 ref/computed）。
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { fetchModelSettings, saveModelSettings, testModelSettings } from '@/api/settings'
import type { ModelSettings, ModelSettingsPayload, ModelTestResult } from '@/types/api'

export const useSettingsStore = defineStore('settings', () => {
  const model = ref<ModelSettings | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const testing = ref(false)
  const loaded = ref(false)

  /**
   * 顶栏那个标签显示什么：
   * - 内置演示显示 `fake`（这时 model 可能是上次留下的 deepseek-chat，会误导）
   * - 真模型显示模型名
   */
  const modelLabel = computed(() => {
    const current = model.value
    if (!current) return '未配置'
    if (current.provider === 'fake') return 'fake'
    return current.model || current.provider
  })

  /** 当前用的是「环境变量继承」还是「自己保存的」 */
  const inherited = computed(() => model.value?.inherited_from_env ?? true)

  async function load(force = false) {
    if (loaded.value && !force) return model.value
    loading.value = true
    try {
      model.value = await fetchModelSettings()
      loaded.value = true
      return model.value
    } finally {
      loading.value = false
    }
  }

  async function save(payload: ModelSettingsPayload) {
    saving.value = true
    try {
      model.value = await saveModelSettings(payload)
      loaded.value = true
      return model.value
    } finally {
      saving.value = false
    }
  }

  async function test(payload: ModelSettingsPayload = {}): Promise<ModelTestResult> {
    testing.value = true
    try {
      return await testModelSettings(payload)
    } finally {
      testing.value = false
    }
  }

  /** 退出登录/注销后清空，避免下一个账号看到上一个人的模型名 */
  function reset() {
    model.value = null
    loaded.value = false
  }

  return {
    model,
    loading,
    saving,
    testing,
    loaded,
    modelLabel,
    inherited,
    load,
    save,
    test,
    reset,
  }
})
