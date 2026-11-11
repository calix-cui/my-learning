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
  const height = panel.value?.offsetHeight ?? 0
  const left = props.align === 'end' ? rect.right - width : rect.left

  // 下方放不下就翻到上方（用户区在侧栏底部，否则菜单会掉出屏幕）
  const below = rect.bottom + 6
  const overflows = height > 0 && below + height > window.innerHeight - 8
  const top = overflows ? Math.max(8, rect.top - height - 6) : below

  position.value = {
    top,
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
    focusItem(0)
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

function menuItems(): HTMLButtonElement[] {
  return Array.from(panel.value?.querySelectorAll<HTMLButtonElement>('.my-menu__item') ?? [])
}

function focusItem(index: number) {
  const list = menuItems()
  if (!list.length) return
  const target = list[(index + list.length) % list.length]
  target.focus({ preventScroll: true })
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    close()
    return
  }
  if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return

  const list = menuItems()
  if (!list.length) return
  event.preventDefault()
  const current = list.indexOf(document.activeElement as HTMLButtonElement)
  const step = event.key === 'ArrowDown' ? 1 : -1
  focusItem(current === -1 ? 0 : current + step)
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
  <div ref="trigger" class="my-menu__trigger">
    <slot :toggle="toggle" :open="open" />
  </div>

  <Teleport to="body">
    <Transition name="my-menu-fade">
      <ul v-if="open" ref="panel" class="my-menu" :style="panelStyle" role="menu">
        <li v-for="item in items" :key="item.key">
          <button
            type="button"
            class="my-menu__item"
            :class="{ 'my-menu__item--danger': item.variant === 'danger' }"
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
  display: flex;
  width: 100%;
  min-width: 0;
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
