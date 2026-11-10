<script setup lang="ts">
/**
 * 柔和按钮：用阴影当边界，不用 1px 线条。
 * 目前只有「新建会话」「重试」这类次级动作使用；主按钮仍是 el-button primary。
 */
withDefaults(defineProps<{ block?: boolean; disabled?: boolean }>(), {
  block: false,
  disabled: false,
})
</script>

<template>
  <button
    type="button"
    class="soft-button"
    :class="{ 'soft-button--block': block }"
    :disabled="disabled"
  >
    <slot />
  </button>
</template>

<style scoped>
.soft-button {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
  height: 40px;
  padding: 0 16px;
  font: inherit;
  font-size: 14px;
  font-weight: 500;
  color: var(--ma-color-ink);
  cursor: pointer;
  background: var(--ma-color-surface);
  border: 0;
  border-radius: 999px;
  box-shadow:
    0 1px 2px rgb(28 27 24 / 6%),
    0 2px 8px rgb(28 27 24 / 4%);
  transition:
    box-shadow 0.18s ease,
    background-color 0.18s ease;
}

.soft-button:hover {
  box-shadow:
    0 2px 6px rgb(28 27 24 / 10%),
    0 8px 20px rgb(28 27 24 / 8%);
}

.soft-button:active {
  box-shadow: 0 1px 2px rgb(28 27 24 / 10%);
}

.soft-button:focus-visible {
  outline: 2px solid var(--ma-color-accent);
  outline-offset: 2px;
}

.soft-button:disabled {
  color: var(--ma-color-faint);
  cursor: not-allowed;
  box-shadow: none;
}

.soft-button--block {
  width: 100%;
}
</style>
