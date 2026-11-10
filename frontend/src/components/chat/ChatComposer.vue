<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { Promotion } from '@element-plus/icons-vue'

const props = defineProps<{
  modelValue: string
  sending: boolean
  disabled: boolean
  maxLength: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: []
}>()

const focused = ref(false)
const textarea = ref<HTMLTextAreaElement | null>(null)

const value = computed({
  get: () => props.modelValue,
  set: (next: string) => emit('update:modelValue', next),
})

const counter = computed(() => `${props.modelValue.length} / ${props.maxLength}`)
const canSend = computed(
  () => !props.sending && !props.disabled && props.modelValue.trim().length > 0,
)

/** Enter 发送、Shift+Enter 换行；输入法组合中不触发（避免拼音上屏就发出去） */
function handleKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  event.preventDefault()
  submit()
}

function submit() {
  if (!canSend.value) return
  emit('send')
}

/** 发送后把焦点留在输入框，键盘用户可以连续输入 */
async function focus() {
  await nextTick()
  textarea.value?.focus()
}

defineExpose({ focus })
</script>

<template>
  <div class="chat__composer">
    <div class="composer__inner">
      <div class="composer__box" :class="{ 'is-focus': focused }">
        <textarea
          ref="textarea"
          v-model="value"
          class="composer__input"
          aria-label="消息内容"
          :maxlength="maxLength"
          :disabled="disabled"
          placeholder="输入消息，Enter 发送，Shift + Enter 换行"
          rows="2"
          @focus="focused = true"
          @blur="focused = false"
          @keydown="handleKeydown"
        />
        <div class="composer__bar">
          <span class="composer__count">{{ counter }}</span>
          <el-button
            type="primary"
            class="composer__send"
            :disabled="!canSend"
            :loading="sending"
            @click="submit"
          >
            <el-icon v-if="!sending"><Promotion /></el-icon>
            <span>{{ sending ? '回复中' : '发送' }}</span>
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat__composer {
  flex: none;
  padding: 12px 32px 24px;
}

.composer__inner {
  max-width: var(--ma-reading-width);
  margin: 0 auto;
}

.composer__box {
  padding: 14px 16px 10px;
  background: var(--ma-color-surface);
  border: 1px solid var(--ma-color-line);
  border-radius: var(--ma-radius-xl);
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.composer__box.is-focus {
  border-color: var(--ma-color-accent);
  box-shadow: 0 0 0 3px var(--ma-color-accent-soft);
}

/* 未聚焦也保留一层极淡的投影，让输入盒从纸面浮起来 */
.composer__box {
  box-shadow: var(--ma-shadow-soft);
}

.composer__input {
  display: block;
  width: 100%;
  min-height: 52px;
  max-height: 160px;
  padding: 0;
  font: inherit;
  font-size: 15px;
  line-height: 1.7;
  color: var(--ma-color-ink);
  resize: none;
  background: none;
  border: 0;
  outline: none;
}

.composer__input::placeholder {
  color: var(--ma-color-faint);
}

.composer__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 4px;
}

.composer__count {
  font-size: 12px;
  color: var(--ma-color-faint);
  font-variant-numeric: tabular-nums;
}

.composer__send {
  height: 32px;
  padding: 0 14px;
  font-size: 13px;
}
</style>
