<script setup lang="ts">
/**
 * 侧栏里的单个会话项。
 *
 * 交互约定：整行可点进入会话；hover 才出现「...」；「...」打开菜单（重命名 / 删除）。
 * 选中态只靠背景色，不加左侧竖条——竖条属于「多余的边界」。
 */
import type { ChatConversationListItem } from '@/types/api'
import AppIcon from '@/components/ui/AppIcon.vue'
import IconButton from '@/components/ui/IconButton.vue'
import MyDropdownMenu, { type MenuItem } from '@/components/ui/MyDropdownMenu.vue'

defineProps<{ item: ChatConversationListItem; active: boolean }>()
const emit = defineEmits<{ open: []; rename: []; remove: [] }>()

const menuItems: MenuItem[] = [
  { key: 'rename', label: '重命名', icon: 'edit' },
  { key: 'remove', label: '删除', icon: 'trash', variant: 'danger', divided: true },
]

function handleCommand(command: string) {
  if (command === 'rename') emit('rename')
  if (command === 'remove') emit('remove')
}
</script>

<template>
  <div class="chat__item" :class="{ 'chat__item--active': active }">
    <button
      type="button"
      class="chat__item-main"
      :aria-current="active ? 'true' : undefined"
      @click="emit('open')"
    >
      <span class="chat__item-title">{{ item.title }}</span>
    </button>

    <span class="chat__item-actions">
      <MyDropdownMenu :items="menuItems" @select="handleCommand">
        <template #default="{ toggle }">
          <IconButton label="更多操作" :size="26" @click="toggle">
            <AppIcon name="more" :size="16" />
          </IconButton>
        </template>
      </MyDropdownMenu>
    </span>
  </div>
</template>

<style scoped>
.chat__item {
  position: relative;
  display: flex;
  align-items: center;
  border-radius: var(--ma-radius-md);
  transition: background-color 0.15s ease;
}

.chat__item:hover {
  background: color-mix(in srgb, var(--ma-color-ink) 5%, transparent);
}

/* 选中项 hover 时保持选中色，避免鼠标一划过就「看起来被取消选中」 */
.chat__item--active:hover {
  background: var(--ma-color-accent-soft);
}

.chat__item--active {
  background: var(--ma-color-accent-soft);
}

.chat__item-main {
  display: flex;
  flex: 1;
  min-width: 0;
  padding: 10px;
  font: inherit;
  text-align: left;
  cursor: pointer;
  background: none;
  border: 0;
  border-radius: inherit;
}

.chat__item-title {
  overflow: hidden;
  font-size: 14px;
  color: var(--ma-color-ink);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat__item-actions {
  display: flex;
  flex: none;
  align-items: center;
  padding-right: 6px;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.chat__item:hover .chat__item-actions,
.chat__item--active .chat__item-actions,
.chat__item-actions:focus-within {
  opacity: 1;
}

@media (prefers-reduced-motion: reduce) {
  .chat__item,
  .chat__item-actions {
    transition: none;
  }
}
</style>
