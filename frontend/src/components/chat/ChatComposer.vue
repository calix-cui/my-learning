<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'

const props = defineProps<{
  modelValue: string
  sending: boolean
  disabled: boolean
  maxLength: number
  agentMode: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: []
  'toggle-agent-mode': []
}>()

const focused = ref(false)
const textarea = ref<HTMLTextAreaElement | null>(null)

const value = computed({
  get: () => props.modelValue,
  set: (next: string) => emit('update:modelValue', next),
})

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
    <div class="composer__box" :class="{ 'is-focus': focused }">
      <textarea
        ref="textarea"
        v-model="value"
        class="composer__input"
        aria-label="消息内容"
        :maxlength="maxLength"
        :disabled="disabled"
        placeholder="给 My Agent 发送消息"
        rows="1"
        @focus="focused = true"
        @blur="focused = false"
        @keydown="handleKeydown"
      />

      <div class="composer__bar">
        <button
          type="button"
          class="chat__mode"
          :class="{ 'is-on': agentMode }"
          :aria-pressed="agentMode"
          title="打开后会先思考、必要时调用工具，再给出回答"
          @click="emit('toggle-agent-mode')"
        >
          <AppIcon name="sparkle" :size="15" />
          深度回答
        </button>

        <el-button
          type="primary"
          circle
          class="composer__send"
          :disabled="!canSend"
          :loading="sending"
          aria-label="发送"
          @click="submit"
        >
          <AppIcon v-if="!sending" name="send" :size="17" />
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat__composer {
  flex: none;
  padding: 8px 32px 24px;
}

.composer__box {
  max-width: var(--ma-reading-width);
  padding: 14px 16px 12px;
  margin: 0 auto;
  background: var(--ma-color-surface);
  border-radius: var(--ma-radius-xl);
  box-shadow: var(--ma-shadow-soft);
  transition: box-shadow 0.18s ease;
}

.composer__box.is-focus {
  box-shadow: var(--ma-shadow-float);
}

.composer__input {
  display: block;
  width: 100%;
  min-height: 48px;
  max-height: 200px;
  padding: 4px 2px;
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
  padding-top: 8px;
}

/* 「深度回答」是一枚可开关的胶囊，状态靠底色与文字色区分，不加边框 */
.chat__mode {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  height: 32px;
  padding: 0 12px;
  font: inherit;
  font-size: 13px;
  color: var(--ma-color-muted);
  cursor: pointer;
  background: color-mix(in srgb, var(--ma-color-ink) 5%, transparent);
  border: 0;
  border-radius: 999px;
  transition:
    background-color 0.15s ease,
    color 0.15s ease;
}

.chat__mode:hover {
  color: var(--ma-color-ink);
  background: color-mix(in srgb, var(--ma-color-ink) 8%, transparent);
}

.chat__mode.is-on {
  color: var(--ma-color-accent);
  background: var(--ma-color-accent-soft);
}

.chat__mode:focus-visible {
  outline: 2px solid var(--ma-color-accent);
  outline-offset: 2px;
}

.composer__send {
  width: 34px;
  height: 34px;
  padding: 0;
}

.composer__send.is-disabled {
  color: var(--ma-color-faint);
  background: color-mix(in srgb, var(--ma-color-ink) 6%, transparent);
}
</style>
