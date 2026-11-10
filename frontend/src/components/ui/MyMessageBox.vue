<script setup lang="ts">
/**
 * 确认/输入弹窗（替代 el-message-box），样式见设计稿：标题 + 一行说明 + 右下角两个按钮。
 *
 * 用法：`await confirmDialog({...})` / `await promptDialog({...})`，
 * 宿主由 `App.vue` 挂一次，状态放在 `messageBoxState` 里，避免每个调用点都写模板。
 */
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'
import { cancelBox, confirmBox, messageBoxState } from '@/components/ui/messageBox'

const input = ref<HTMLInputElement | null>(null)
const error = ref('')
const value = ref('')

watch(
  () => messageBoxState.options,
  async (options) => {
    value.value = options?.input?.value ?? ''
    error.value = ''
    await nextTick()
    input.value?.focus()
    input.value?.select()
  },
)

function submit() {
  if (!messageBoxState.options) return
  const validator = messageBoxState.options.input?.validator
  if (validator) {
    const result = validator(value.value)
    if (result !== true) {
      error.value = typeof result === 'string' ? result : '输入不合法'
      return
    }
  }
  confirmBox(messageBoxState.options.input ? value.value : true)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') cancelBox()
  if (event.key === 'Enter' && messageBoxState.options?.input) submit()
}

// 弹窗挂在 body 上，键盘事件直接听 document，避免给 section 绑交互处理器
watch(
  () => messageBoxState.open,
  (open) => {
    if (open) document.addEventListener('keydown', onKeydown)
    else document.removeEventListener('keydown', onKeydown)
  },
)

onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <Transition name="my-box-fade">
      <div v-if="messageBoxState.open && messageBoxState.options" class="my-box-layer">
        <button type="button" class="my-box-layer__scrim" aria-label="取消" @click="cancelBox" />

        <section
          class="my-box"
          role="dialog"
          aria-modal="true"
          :aria-label="messageBoxState.options.title"
        >
          <h2 class="my-box__title">{{ messageBoxState.options.title }}</h2>
          <p v-if="messageBoxState.options.description" class="my-box__desc">
            {{ messageBoxState.options.description }}
          </p>

          <div v-if="messageBoxState.options.input" class="my-box__field">
            <span class="my-box__label" aria-hidden="true">
              {{ messageBoxState.options.input.label ?? '输入内容' }}
            </span>
            <input
              ref="input"
              v-model="value"
              class="my-box__input"
              :aria-label="messageBoxState.options.input.label ?? '输入内容'"
              :placeholder="messageBoxState.options.input.placeholder"
              :aria-invalid="error ? 'true' : undefined"
            />
            <span v-if="error" class="my-box__error">{{ error }}</span>
          </div>

          <div class="my-box__actions">
            <button type="button" class="my-box__btn" @click="cancelBox">
              {{ messageBoxState.options.cancelText ?? '取消' }}
            </button>
            <button
              type="button"
              class="my-box__btn my-box__btn--primary"
              :class="{ 'is-danger': messageBoxState.options.danger }"
              @click="submit"
            >
              <AppIcon v-if="messageBoxState.options.danger" name="trash" :size="15" />
              {{ messageBoxState.options.confirmText ?? '确定' }}
            </button>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.my-box-layer {
  position: fixed;
  inset: 0;
  z-index: 2100;
  display: grid;
  place-items: center;
  padding: 24px;
  background: color-mix(in srgb, var(--ma-color-ink) 28%, transparent);
}

.my-box-layer__scrim {
  position: absolute;
  inset: 0;
  padding: 0;
  cursor: default;
  background: transparent;
  border: 0;
}

.my-box {
  position: relative;
  width: min(420px, 100%);
  padding: 24px 24px 18px;
  background: var(--ma-color-surface);
  border-radius: var(--ma-radius-xl);
  box-shadow: var(--ma-shadow-float);
}

.my-box__title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.my-box__desc {
  margin: 10px 0 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--ma-color-muted);
}

.my-box__field {
  display: block;
  margin-top: 16px;
}

.my-box__label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--ma-color-muted);
}

.my-box__input {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  font: inherit;
  color: var(--ma-color-ink);
  background: var(--ma-color-canvas);
  border: 0;
  border-radius: var(--ma-radius-md);
  box-shadow: inset 0 0 0 1px var(--ma-color-line);
}

.my-box__input:focus {
  outline: none;
  box-shadow:
    inset 0 0 0 1px var(--ma-color-accent),
    0 0 0 3px var(--ma-color-accent-soft);
}

.my-box__error {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  color: var(--ma-color-danger);
}

.my-box__actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 22px;
}

.my-box__btn {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  height: 38px;
  padding: 0 18px;
  font: inherit;
  font-size: 14px;
  font-weight: 500;
  color: var(--ma-color-ink);
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: 999px;
  box-shadow: inset 0 0 0 1px var(--ma-color-line);
  transition:
    background-color 0.15s ease,
    box-shadow 0.15s ease;
}

.my-box__btn:hover {
  background: color-mix(in srgb, var(--ma-color-ink) 5%, transparent);
}

.my-box__btn--primary {
  color: var(--ma-color-on-accent);
  background: var(--ma-color-accent);
  box-shadow: none;
}

.my-box__btn--primary:hover {
  background: var(--ma-color-accent-hover);
}

.my-box__btn--primary.is-danger {
  color: #fff;
  background: var(--ma-color-danger);
}

.my-box__btn--primary.is-danger:hover {
  background: color-mix(in srgb, var(--ma-color-danger) 88%, #000);
}

.my-box__btn:focus-visible {
  outline: 2px solid var(--ma-color-accent);
  outline-offset: 2px;
}

.my-box-fade-enter-active,
.my-box-fade-leave-active {
  transition: opacity 0.16s ease;
}

.my-box-fade-enter-from,
.my-box-fade-leave-to {
  opacity: 0;
}
</style>
