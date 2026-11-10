<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import ThreadList from '@/components/chat/ThreadList.vue'
import SettingsDialog from '@/components/settings/SettingsDialog.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import MyDropdownMenu, { type MenuItem } from '@/components/ui/MyDropdownMenu.vue'
import MyMessageBox from '@/components/ui/MyMessageBox.vue'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const chat = useChatStore()
const settings = useSettingsStore()
const theme = useThemeStore()

/** 登录/注册页不套应用外壳（没有侧边栏与对话区） */
const isAuthPage = computed(() => route.meta.public === true)

/**
 * 设置是悬浮窗而不是独立页面：`/settings` 仍可深链，进来就把窗打开，
 * 关窗回到对话页——这样既满足「不打断当前会话」，也保住了旧链接。
 */
const settingsOpen = ref(false)

watch(
  () => route.query.settings,
  (flag) => {
    if (flag === '1') settingsOpen.value = true
  },
  { immediate: true },
)

function closeSettings() {
  settingsOpen.value = false
  if (route.query.settings) void router.replace({ path: '/chat' })
}

/**
 * 顶栏那个模型标签用「账号里配置的模型」，拿不到就退回上一条回复的模型。
 *
 * 必须 watch 而不是只在 onMounted 里取：App 只在启动时挂载一次，
 * 首屏是登录页时 onMounted 里还没登录，登录完成后要再取一次。
 */
watch(
  () => session.isLoggedIn,
  (loggedIn) => {
    if (loggedIn) {
      void settings.load().catch(() => undefined)
      // 账号存过外观就以账号为准；没存过会把本机偏好写上去
      void theme.syncFromAccount()
    }
  },
  { immediate: true },
)

async function handleLogout() {
  await session.logout()
  chat.reset()
  settings.reset()
  ElMessage.success('已退出登录')
  await router.replace({ name: 'login' })
}

const userMenuItems: MenuItem[] = [
  { key: 'settings', label: '系统设置', icon: 'settings' },
  { key: 'logout', label: '退出登录', icon: 'logout' },
]

async function handleUserCommand(command: string) {
  if (command === 'logout') {
    await handleLogout()
    return
  }
  if (command === 'settings') {
    settingsOpen.value = true
    await router.replace({ path: '/chat', query: { settings: '1' } })
  }
}
</script>

<template>
  <MyMessageBox />

  <router-view v-if="isAuthPage" />

  <div v-else class="layout">
    <aside class="layout__aside">
      <div class="layout__brand">
        <img class="layout__logo" src="/logo.png" alt="" width="28" height="28" />
        <span class="layout__brand-text">My Agent</span>
      </div>

      <ThreadList class="layout__threads" />

      <div class="layout__aside-footer">
        <MyDropdownMenu :items="userMenuItems" align="start" @select="handleUserCommand">
          <template #default="{ toggle }">
            <div
              class="layout__user-trigger"
              role="button"
              tabindex="0"
              aria-label="账号菜单"
              @click="toggle"
              @keydown.enter.prevent="toggle"
              @keydown.space.prevent="toggle"
            >
              <span class="layout__avatar">{{ session.avatarText }}</span>
              <span class="layout__user-name">{{ session.displayName }}</span>
              <AppIcon name="more" :size="16" class="layout__user-more" />
            </div>
          </template>
        </MyDropdownMenu>
      </div>
    </aside>

    <main class="layout__main">
      <div class="layout__content">
        <router-view />
      </div>
    </main>

    <SettingsDialog v-model:open="settingsOpen" @close="closeSettings" />
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--ma-color-canvas);
}

.layout__aside {
  display: flex;
  flex: none;
  flex-direction: column;
  width: var(--ma-sidebar-width);
  padding: 18px 14px 12px;
  background: var(--ma-color-canvas);
  border-right: 1px solid var(--ma-color-line);
}

.layout__brand {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 2px 10px 20px;
}

.layout__logo {
  border-radius: 8px;
}

.layout__brand-text {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.layout__threads {
  flex: 1;
  min-height: 0;
}

.layout__aside-footer {
  display: flex;
  flex: none;
  gap: 4px;
  align-items: center;
  padding-top: 8px;
  margin-top: 8px;
}

.layout__user-trigger {
  display: flex;
  flex: 1;
  gap: 10px;
  align-items: center;
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

.layout__user-trigger:hover {
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--ma-color-ink) 7%, transparent),
    color-mix(in srgb, var(--ma-color-ink) 3%, transparent)
  );
}

.layout__user-trigger:focus-visible {
  outline: 2px solid var(--ma-color-accent);
  outline-offset: -2px;
}

.layout__avatar {
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

.layout__user-text {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  line-height: 1.4;
}

.layout__user-name {
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.layout__user-mail {
  overflow: hidden;
  font-size: 12px;
  color: var(--ma-color-faint);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.layout__user-arrow {
  flex: none;
  font-size: 12px;
  color: var(--ma-color-faint);
}

.layout__settings-link {
  flex: none;
  color: var(--ma-color-muted);
}

.layout__main {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

/* 主区内容最大 1080，超出居中；页面自己决定是否再收窄（对话页 720） */
.layout__content {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.layout__content > * {
  width: 100%;
  max-width: var(--ma-content-width);
  margin: 0 auto;
}

@media (width < 960px) {
  .layout__aside {
    width: 220px;
  }
}
</style>
