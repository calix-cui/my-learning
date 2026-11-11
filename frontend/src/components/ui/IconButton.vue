<script setup lang="ts">
/**
 * 圆形图标按钮：侧栏「...」、工具栏分享、关闭设置这类低频动作统一用它。
 * 规则（见 DESIGN.md）：默认无边框、无背景；hover 加深一层背景；不做位移与放大。
 */
withDefaults(
  defineProps<{
    label: string
    size?: number
    active?: boolean
  }>(),
  { size: 32, active: false },
)
</script>

<template>
  <button
    type="button"
    class="icon-button u-tint"
    :class="{ 'is-active': active }"
    :style="{ width: `${size}px`, height: `${size}px` }"
    :aria-label="label"
    :title="label"
  >
    <slot />
  </button>
</template>

<style scoped>
.icon-button {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  padding: 0;
  color: var(--ma-color-muted);
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: 999px;
  transition: color var(--ma-motion-hover) ease;
}

.icon-button:hover {
  color: var(--ma-color-ink);
}

.icon-button.is-active,
.icon-button:active {
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--ma-color-ink) 12%, transparent),
    color-mix(in srgb, var(--ma-color-ink) 7%, transparent)
  );
}

.icon-button.icon-button.is-active::before,
.icon-button.icon-button.is-active:hover::before,
.icon-button.icon-button:active::before {
  opacity: 0;
}

.icon-button:focus-visible {
  outline: 2px solid var(--ma-color-accent);
  outline-offset: 1px;
}
</style>
