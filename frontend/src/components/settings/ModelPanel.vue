<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'

import { useSettingsStore } from '@/stores/settings'
import type { ModelSettingsPayload } from '@/types/api'

/**
 * 模型接入：provider 分段 + 四项表单 + 测试连接。
 *
 * Key 的三态在界面上这样映射：
 * - 输入框留空 → 不传 api_key（沿用已保存的）；
 * - 点「更换」后输入新值 → 传新值，保存后只显示末四位；
 * - 点「清除」 → 传空串。
 */
const settingsStore = useSettingsStore()
const { model, saving, testing } = storeToRefs(settingsStore)

const form = reactive({
  provider: 'fake' as 'fake' | 'openai',
  base_url: '',
  model: '',
  timeout_seconds: 30,
})

const apiKey = ref('')
/** 打开「更换 Key」后输入框才可编辑 */
const editingKey = ref(false)
const testResult = ref<{ ok: boolean; message: string; latency_ms: number } | null>(null)

const hasSavedKey = computed(() => model.value?.has_api_key ?? false)
const keyHint = computed(() => model.value?.api_key_hint ?? '')
const canStoreKey = computed(() => model.value?.can_store_api_key ?? false)
const inherited = computed(() => model.value?.inherited_from_env ?? true)

function fillForm() {
  const current = model.value
  if (!current) return
  form.provider = current.provider
  form.base_url = current.base_url ?? ''
  form.model = current.model ?? ''
  form.timeout_seconds = current.timeout_seconds
}

onMounted(async () => {
  await settingsStore.load()
  fillForm()
})

function buildPayload(): ModelSettingsPayload {
  const payload: ModelSettingsPayload = {
    provider: form.provider,
    base_url: form.base_url.trim() || null,
    model: form.model.trim() || null,
    timeout_seconds: form.timeout_seconds,
  }
  if (editingKey.value) {
    payload.api_key = apiKey.value.trim()
  }
  return payload
}

async function handleTest() {
  testResult.value = null
  const payload = buildPayload()
  // 编辑中但还没填新 Key，就按「不传」处理，用已保存的那把测
  if (editingKey.value && !apiKey.value.trim()) {
    delete payload.api_key
  }
  try {
    const result = await settingsStore.test(payload)
    testResult.value = result
    if (result.ok) {
      ElMessage.success(`连接正常（${result.latency_ms} ms）`)
    } else {
      ElMessage.error(result.message)
    }
  } catch {
    // 错误提示由拦截器统一弹
  }
}

async function handleSave() {
  try {
    await settingsStore.save(buildPayload())
    editingKey.value = false
    apiKey.value = ''
    fillForm()
    testResult.value = null
    ElMessage.success('模型设置已保存')
  } catch {
    // 同上
  }
}

function startEditKey() {
  editingKey.value = true
  apiKey.value = ''
}

async function clearKey() {
  try {
    await settingsStore.save({ api_key: '' })
    ElMessage.success('已清除保存的 Key，后续使用环境变量里的配置')
  } catch {
    // 同上
  }
}
</script>

<template>
  <section class="model">
    <header class="model__head">
      <h2 class="model__title">模型接入</h2>
      <p class="model__desc">
        支持任何 OpenAI 兼容服务。Key 加密后存在你自己的账号下，界面只显示末四位。
      </p>
    </header>

    <p v-if="inherited" class="model__notice">
      当前用的是服务端环境变量里的配置，还没有为这个账号单独保存过。
    </p>

    <div class="model__block">
      <h3 class="model__label">服务类型</h3>
      <div class="model__seg" role="radiogroup" aria-label="服务类型">
        <button
          v-for="option in [
            { value: 'openai', label: 'OpenAI 兼容' },
            { value: 'fake', label: '内置演示（fake）' },
          ]"
          :key="option.value"
          type="button"
          role="radio"
          :aria-checked="form.provider === option.value"
          class="model__seg-item"
          :class="{ 'is-active': form.provider === option.value }"
          @click="form.provider = option.value as 'fake' | 'openai'"
        >
          {{ option.label }}
        </button>
      </div>
      <p class="model__hint">
        选「内置演示」时不会联网，回复固定为
        <code>[fake] 收到：…</code>，适合本地跑通链路。
      </p>
    </div>

    <template v-if="form.provider === 'openai'">
      <div class="model__block">
        <span class="model__label">Base URL</span>
        <el-input
          v-model="form.base_url"
          aria-label="Base URL"
          placeholder="https://api.deepseek.com/v1"
          autocomplete="off"
        />
        <p class="model__hint">末尾带 /v1；请求会打到 <code>{base}/chat/completions</code>。</p>
      </div>

      <div class="model__block">
        <span class="model__label">API Key</span>
        <div class="model__key">
          <el-input
            v-if="editingKey"
            v-model="apiKey"
            aria-label="新的 API Key"
            type="password"
            show-password
            placeholder="粘贴新的 Key，保存后只显示末四位"
            autocomplete="new-password"
          />
          <el-input
            v-else
            :model-value="hasSavedKey ? `••••••••••••••••${keyHint ?? ''}` : ''"
            readonly
            placeholder="还没有保存 Key，当前使用环境变量里的配置"
          />
          <el-button v-if="!editingKey" @click="startEditKey">更换</el-button>
          <el-button v-else @click="editingKey = false">取消</el-button>
        </div>
        <p v-if="!canStoreKey" class="model__warn">
          服务端没有配置 APP_SECRET_KEY，暂时不能保存自定义 Key（其他字段仍可保存）。
        </p>
        <div v-else-if="hasSavedKey && !inherited" class="model__key-actions">
          <el-button link type="danger" @click="clearKey">清除已保存的 Key</el-button>
        </div>
        <p class="model__hint">保存后不可再查看全文；忘记就只能重新填一个。</p>
      </div>

      <div class="model__block">
        <span class="model__label">模型名</span>
        <el-input aria-label="模型名" v-model="form.model" placeholder="deepseek-chat" />
      </div>
    </template>

    <div class="model__block">
      <span class="model__label">超时（秒）</span>
      <el-input-number v-model="form.timeout_seconds" aria-label="超时秒数" :min="5" :max="300" />
      <p class="model__hint">本地大模型建议 120 以上；超过这个时间会返回 504。</p>
    </div>

    <div class="model__footer">
      <div v-if="testResult" class="model__result" :class="{ 'is-bad': !testResult.ok }">
        <span>{{ testResult.message }}</span>
        <span v-if="testResult.ok" class="model__result-meta">{{ testResult.latency_ms }} ms</span>
      </div>
      <div class="model__actions">
        <el-button :loading="testing" @click="handleTest">测试连接</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.model__head {
  margin-bottom: 20px;
}

.model__title {
  font-size: 20px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.model__desc {
  margin-top: 4px;
  font-size: 13px;
  color: var(--ma-color-muted);
}

.model__notice {
  padding: 10px 12px;
  margin-bottom: 20px;
  font-size: 13px;
  color: var(--ma-color-muted);
  background: var(--ma-color-sunken);
  border-radius: var(--ma-radius-sm);
}

.model__block + .model__block {
  margin-top: 20px;
}

.model__label {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.model__seg {
  display: inline-flex;
  padding: 3px;
  background: var(--ma-color-sunken);
  border-radius: var(--ma-radius-sm);
}

.model__seg-item {
  padding: 6px 14px;
  font: inherit;
  font-size: 13px;
  color: var(--ma-color-muted);
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: 5px;
}

.model__seg-item.is-active {
  font-weight: 600;
  color: var(--ma-color-ink);
  background: var(--ma-color-surface);
  box-shadow: var(--ma-shadow-sm);
}

.model__seg-item:focus-visible {
  outline: 2px solid var(--ma-color-accent);
  outline-offset: 1px;
}

.model__key {
  display: flex;
  gap: 8px;
  align-items: center;
}

.model__key :deep(.el-input) {
  flex: 1;
}

.model__key-actions {
  margin-top: 6px;
}

.model__hint {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--ma-color-muted);
}

.model__hint code {
  padding: 1px 5px;
  font-family: var(--ma-font-mono);
  font-size: 12px;
  background: var(--ma-color-sunken);
  border-radius: 4px;
}

.model__warn {
  margin-top: 6px;
  font-size: 12px;
  color: var(--ma-color-warn);
}

.model__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 20px;
  margin-top: 24px;
  border-top: 1px solid var(--ma-color-line);
}

.model__result {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  color: var(--ma-color-success);
}

.model__result.is-bad {
  color: var(--ma-color-danger);
}

.model__result-meta {
  color: var(--ma-color-muted);
}

.model__actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}
</style>
