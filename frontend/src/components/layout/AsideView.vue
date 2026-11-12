<script setup lang="ts">
/**
 * 左栏：品牌、会话列表、账号区。
 *
 * 会话列表属于侧栏，挂载时就在这里拉一次——不放在对话页里，
 * 免得「谁负责加载侧栏数据」和「谁负责渲染侧栏」分在两个组件。
 */
import { onMounted } from 'vue'

import ThreadList from '@/components/chat/ThreadList.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import MyDropdownMenu, { type MenuItem } from '@/components/ui/MyDropdownMenu.vue'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'

const emit = defineEmits<{ settings: []; logout: [] }>()

const chat = useChatStore()
const session = useSessionStore()

const userMenuItems: MenuItem[] = [
  { key: 'settings', label: '系统设置', icon: 'settings' },
  { key: 'logout', label: '退出登录', icon: 'logout' },
]

function handleCommand(key: string) {
  if (key === 'settings') emit('settings')
  if (key === 'logout') emit('logout')
}

onMounted(() => {
  // 侧栏只在已登录时存在；未登录时别拉列表，401 会被拦截器改写成「跳登录」
  if (session.isLoggedIn) void chat.ensureConversationsLoaded()
})
</script>

<template>
  <aside class="aside">
    <div class="aside__brand">
      <img class="aside__logo" src="/logo.png" alt="" width="28" height="28" />
      <span class="aside__brand-text">My Agent</span>
    </div>

    <ThreadList class="aside__threads" />

    <div class="aside__footer">
      <MyDropdownMenu :items="userMenuItems" align="start" @select="handleCommand">
        <template #default="{ toggle }">
          <div
            class="aside__user-trigger u-tint"
            role="button"
            tabindex="0"
            aria-label="账号菜单"
            @click="toggle"
            @keydown.enter.prevent="toggle"
            @keydown.space.prevent="toggle"
          >
            <span class="aside__user-info">
              <span class="aside__avatar">{{ session.avatarText }}</span>
              <span class="aside__user-name">{{ session.displayName }}</span>
            </span>
            <AppIcon name="more" :size="16" class="aside__user-more" />
          </div>
        </template>
      </MyDropdownMenu>
    </div>
  </aside>
</template>

<style scoped>
.aside {
  display: flex;
  flex: none;
  flex-direction: column;
  width: var(--ma-sidebar-width);
  padding: 18px 14px 12px;
  background: var(--ma-color-canvas);
  border-right: 1px solid var(--ma-color-line);
}

.aside__brand {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 2px 10px 20px;
}

.aside__logo {
  border-radius: 8px;
}

.aside__brand-text {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.aside__threads {
  flex: 1;
  min-height: 0;
}

.aside__footer {
  display: flex;
  flex: none;
  gap: 4px;
  align-items: center;
  padding-top: 8px;
  margin-top: 8px;
}

.aside__user-trigger {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
  padding: 8px 10px;
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
  background: none;
  border: 0;
  border-radius: var(--ma-radius-md);
}

.aside__user-trigger:focus-visible {
  outline: 2px solid var(--ma-color-accent);
  outline-offset: -2px;
}

.aside__avatar {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ma-color-accent);
  background: var(--ma-color-accent-soft);
  border-radius: 999px;
}

.aside__user-info {
  display: flex;
  flex: 1;
  gap: 10px;
  align-items: center;
  min-width: 0;
}

.aside__user-name {
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.aside__user-more {
  flex: none;
  color: var(--ma-color-faint);
}

@media (width < 960px) {
  .aside {
    width: 220px;
  }
}
</style>
