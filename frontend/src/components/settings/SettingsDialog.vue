<script setup lang="ts">
/**
 * 设置悬浮窗：盖在当前对话之上，关掉就回到原处——不打断正在进行的会话。
 *
 * 路由 `/settings` 会重定向到 `/chat?settings=1`，因此深链仍然可用，
 * 关闭时把 query 去掉即可。
 */
import { watch } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'
import IconButton from '@/components/ui/IconButton.vue'
import SettingsView from '@/views/SettingsView.vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [value: boolean]; close: [] }>()

function close() {
  emit('update:open', false)
  emit('close')
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') close()
}

// 打开时锁滚动并监听 Esc；关闭时恢复
watch(
  () => props.open,
  (open) => {
    if (open) {
      document.addEventListener('keydown', onKeydown)
      document.body.style.overflow = 'hidden'
    } else {
      document.removeEventListener('keydown', onKeydown)
      document.body.style.overflow = ''
    }
  },
)
</script>

<template>
  <Teleport to="body">
    <Transition name="settings-fade">
      <div v-if="open" class="settings-layer">
        <button type="button" class="settings-layer__scrim" aria-label="关闭设置" @click="close" />
        <section class="settings-window" role="dialog" aria-modal="true" aria-label="设置">
          <header class="settings-window__head">
            <h2 class="settings-window__title">设置</h2>
            <IconButton label="关闭设置" @click="close">
              <AppIcon name="close" :size="18" />
            </IconButton>
          </header>

          <SettingsView class="settings-window__body" />
        </section>
        <button type="button" class="settings-layer__scrim" aria-hidden="true" tabindex="-1" />
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.settings-layer__scrim {
  position: absolute;
  inset: 0;
  padding: 0;
  cursor: default;
  background: transparent;
  border: 0;
}

.settings-layer {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: color-mix(in srgb, var(--ma-color-ink) 28%, transparent);
  backdrop-filter: blur(2px);
}

.settings-window {
  position: relative;
  display: flex;
  flex-direction: column;
  width: min(920px, 100%);
  height: min(680px, 100%);
  overflow: hidden;
  background: var(--ma-color-surface);
  border-radius: var(--ma-radius-xl);
  box-shadow: var(--ma-shadow-float);
}

.settings-window__head {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px 10px 28px;
}

.settings-window__title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.settings-window__body {
  flex: 1;
  min-height: 0;
}

.settings-fade-enter-active,
.settings-fade-leave-active {
  transition: opacity 0.18s ease;
}

.settings-fade-enter-from,
.settings-fade-leave-to {
  opacity: 0;
}
</style>
