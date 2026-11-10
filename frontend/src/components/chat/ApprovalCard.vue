<script setup lang="ts">
import { computed, ref } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'
import type { PendingApproval } from '@/stores/chat'

const props = defineProps<{ approval: PendingApproval; busy?: boolean }>()
const emit = defineEmits<{ decide: [decision: 'approve' | 'reject', note?: string] }>()

const note = ref('')

/** 参数原样展示：用户要看清「模型到底想做什么」才敢点批准 */
const argsText = computed(() => {
  const args = props.approval.args ?? {}
  return Object.keys(args).length ? JSON.stringify(args, null, 2) : '（无参数）'
})

function decide(decision: 'approve' | 'reject') {
  if (props.busy) return
  emit('decide', decision, note.value.trim() || undefined)
  note.value = ''
}
</script>

<template>
  <section class="approval">
    <header class="approval__head">
      <AppIcon name="sparkle" :size="18" />
      <span class="approval__title">需要你确认</span>
      <code class="approval__tool">{{ approval.tool }}</code>
      <span v-if="approval.reason" class="approval__reason">{{ approval.reason }}</span>
    </header>

    <pre class="approval__args">{{ argsText }}</pre>

    <div class="approval__body">
      <input
        id="approval-note"
        v-model="note"
        class="approval__note"
        type="text"
        maxlength="80"
        placeholder="拒绝理由（可留空）"
        aria-label="拒绝理由"
        :disabled="busy"
      />
      <div class="approval__actions">
        <button
          class="approval__btn approval__btn--ghost"
          :disabled="busy"
          @click="decide('reject')"
        >
          拒绝
        </button>
        <button
          class="approval__btn approval__btn--primary"
          :disabled="busy"
          @click="decide('approve')"
        >
          {{ busy ? '执行中…' : '批准执行' }}
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.approval {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 14px;
  padding: 18px 20px;
  background: var(--ma-color-surface);
  border-radius: 18px;
  box-shadow: var(--ma-shadow-soft);
}

.approval__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  color: var(--ma-color-warning-ink, var(--ma-color-ink));
  font-size: 13px;
}

.approval__title {
  font-weight: 600;
}

.approval__tool {
  padding: 2px 8px;
  font-family: var(--ma-font-mono, ui-monospace, monospace);
  font-size: 12px;
  color: var(--ma-color-accent-ink);
  background: var(--ma-color-accent-soft);
  border-radius: 6px;
}

.approval__reason {
  color: var(--ma-color-ink-muted);
}

.approval__args {
  margin: 0;
  padding: 12px 14px;
  overflow-x: auto;
  font-family: var(--ma-font-mono, ui-monospace, monospace);
  font-size: 12px;
  line-height: 1.6;
  color: var(--ma-color-ink-soft);
  background: var(--ma-color-canvas);
  border-radius: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}

.approval__body {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.approval__note {
  flex: 1;
  min-width: 200px;
  height: 34px;
  padding: 0 12px;
  color: var(--ma-color-ink);
  background: var(--ma-color-canvas);
  border: 0;
  border-radius: 10px;
  outline: none;
}

.approval__note:focus-visible {
  box-shadow: inset 0 0 0 1px var(--ma-color-accent);
}

.approval__actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.approval__btn {
  height: 34px;
  padding: 0 16px;
  font-size: 13px;
  color: var(--ma-color-ink);
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: 10px;
  transition: background 0.16s ease;
}

.approval__btn--ghost {
  border: 1px solid var(--ma-color-line);
}

.approval__btn--ghost:hover {
  background: linear-gradient(
    90deg,
    var(--ma-color-ink-wash-strong),
    var(--ma-color-ink-wash-weak)
  );
}

.approval__btn--primary {
  color: var(--ma-color-on-accent);
  background: var(--ma-color-accent);
}

.approval__btn--primary:hover {
  background: var(--ma-color-accent-strong, var(--ma-color-accent));
}

.approval__btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
</style>
