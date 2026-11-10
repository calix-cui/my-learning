<script setup lang="ts">
/**
 * 下拉菜单（替代 el-dropdown）。
 *
 * 结构：默认插槽放触发器，`items` 描述菜单项；点触发器开、点外部/Esc 关。
 * 面板用 fixed 定位（贴触发器右下角），所以放在 `overflow: auto` 的容器里也不会被裁。
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'

export interface MenuItem {
  key: string
  label: string
  icon?: 'edit' | 'trash' | 'settings' | 'logout' | 'share' | 'sparkle' | 'plus'
  /** danger 用红色文字，只给删除、退出这类不可逆动作 */
  variant?: 'normal' | 'danger'
  /** 与前一项之间画一条淡分隔线 */
  divided?: boolean
}

const props = withDefaults(defineProps<{ items: MenuItem[]; align?: 'start' | 'end' }>(), {
  align: 'end',
})
const emit = defineEmits<{ select: [key: string] }>()

const open = ref(false)
const trigger = ref<HTMLElement | null>(null)
const panel = ref<HTMLElement | null>(null)
const position = ref({ top: 0, left: 0 })

const panelStyle = computed(() => ({
  top: `${position.value.top}px`,
  left: `${position.value.left}px`,
}))

function place() {
  const el = trigger.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const width = panel.value?.offsetWidth ?? 180
  const left = props.align === 'end' ? rect.right - width : rect.left
  position.value = {
    top: rect.bottom + 6,
    left: Math.max(8, Math.min(left, window.innerWidth - width - 8)),
  }
}

async function toggle() {
  open.value = !open.value
  if (open.value) {
    await nextTick()
    place()
    document.addEventListener('pointerdown', onOutside, true)
    document.addEventListener('keydown', onKeydown)
  } else {
    detach()
  }
}

function detach() {
  document.removeEventListener('pointerdown', onOutside, true)
  document.removeEventListener('keydown', onKeydown)
}

function onOutside(event: PointerEvent) {
  const target = event.target as Node
  if (panel.value?.contains(target) || trigger.value?.contains(target)) return
  close()
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') close()
}

function close() {
  open.value = false
  detach()
}

function pick(item: MenuItem) {
  close()
  emit('select', item.key)
}

watch(open, (value) => {
  if (!value) detach()
})
onBeforeUnmount(detach)
</script>

<template>
  <span ref="trigger" class="my-menu__trigger">
    <slot :toggle="toggle" :open="open" />
  </span>

  <Teleport to="body">
    <Transition name="my-menu-fade">
      <ul v-if="open" ref="panel" class="my-menu" :style="panelStyle" role="menu">
        <li v-for="item in items" :key="item.key">
          <button
            type="button"
            class="my-menu__item"
            :class="{
              'my-menu__item--danger': item.variant === 'danger',
              'my-menu__item--divided': item.divided,
            }"
            role="menuitem"
            @click="pick(item)"
          >
            <AppIcon v-if="item.icon" :name="item.icon" :size="17" />
            {{ item.label }}
          </button>
        </li>
      </ul>
    </Transition>
  </Teleport>
</template>

<style scoped>
.my-menu__trigger {
  display: inline-flex;
}

.my-menu {
  position: fixed;
  z-index: 2050;
  min-width: 168px;
  padding: 6px;
  margin: 0;
  list-style: none;
  background: var(--ma-color-surface);
  border-radius: var(--ma-radius-lg);
  box-shadow: var(--ma-shadow-float);
}

.my-menu__item {
  display: flex;
  gap: 10px;
  align-items: center;
  width: 100%;
  padding: 9px 12px;
  font: inherit;
  font-size: 14px;
  color: var(--ma-color-ink);
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: var(--ma-radius-sm);
  transition: background 0.15s ease;
}

/* hover 用一层很淡的渐变，避免整块死板的灰 */
.my-menu__item:hover {
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--ma-color-ink) 7%, transparent),
    color-mix(in srgb, var(--ma-color-ink) 3%, transparent)
  );
}

.my-menu__item:active {
  background: color-mix(in srgb, var(--ma-color-ink) 9%, transparent);
}

.my-menu__item--danger {
  color: var(--ma-color-danger);
}

.my-menu__item--danger:hover {
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--ma-color-danger) 10%, transparent),
    color-mix(in srgb, var(--ma-color-danger) 4%, transparent)
  );
}

.my-menu__item--divided {
  position: relative;
}

.my-menu__item--divided::before {
  position: absolute;
  top: -4px;
  right: 8px;
  left: 8px;
  height: 1px;
  content: '';
  background: var(--ma-color-line);
}

.my-menu-fade-enter-active,
.my-menu-fade-leave-active {
  transition:
    opacity 0.14s ease,
    transform 0.14s ease;
}

.my-menu-fade-enter-from,
.my-menu-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
