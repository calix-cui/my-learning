<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowDown, Setting } from '@element-plus/icons-vue'

import ThreadList from '@/components/chat/ThreadList.vue'
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

/** 登录/注册页不套应用外壳（没有侧边栏和顶栏） */
const isAuthPage = computed(() => route.meta.public === true)

const pageTitle = computed(() => (route.meta.title as string | undefined) ?? 'My Agent')
const isChatPage = computed(() => route.name === 'chat')

/** 后端联通状态：null 表示检测中，仅用于顶栏状态点 */
const backendOnline = ref<boolean | null>(null)

onMounted(async () => {
  try {
    const response = await fetch('/healthz')
    backendOnline.value = response.ok
  } catch {
    backendOnline.value = false
  }
})

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

const modelPill = computed(() => {
  const configured = settings.modelLabel
  return configured && configured !== '未配置' ? configured : chat.modelLabel
})

const statusText = computed(() => {
  if (backendOnline.value === null) return '检测中'
  return backendOnline.value ? '已连接' : '未连接'
})

async function handleLogout() {
  await session.logout()
  chat.reset()
  settings.reset()
  ElMessage.success('已退出登录')
  await router.replace({ name: 'login' })
}

async function handleUserCommand(command: string) {
  if (command === 'logout') {
    await handleLogout()
    return
  }
  if (command === 'settings') {
    await router.push({ name: 'settings' })
  }
}
</script>

<template>
  <router-view v-if="isAuthPage" />

  <div v-else class="layout">
    <aside class="layout__aside">
      <div class="layout__brand">
        <img class="layout__logo" src="/logo.png" alt="" width="28" height="28" />
        <span class="layout__brand-text">My Agent</span>
      </div>

      <ThreadList class="layout__threads" />

      <div class="layout__aside-footer">
        <el-dropdown trigger="click" placement="top-start" @command="handleUserCommand">
          <button type="button" class="layout__user-trigger">
            <span class="layout__avatar">{{ session.avatarText }}</span>
            <span class="layout__user-text">
              <span class="layout__user-name">{{ session.displayName }}</span>
              <!-- 没填显示名时 displayName 就是邮箱，避免同一行重复两次 -->
              <span v-if="session.user?.display_name" class="layout__user-mail">
                {{ session.user?.email }}
              </span>
            </span>
            <el-icon class="layout__user-arrow"><ArrowDown /></el-icon>
          </button>

          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="settings">
                <el-icon><Setting /></el-icon>
                设置
              </el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <el-button
          link
          class="layout__settings-link"
          :icon="Setting"
          title="设置"
          @click="router.push({ name: 'settings' })"
        />
      </div>
    </aside>

    <main class="layout__main">
      <header class="layout__topbar">
        <nav class="layout__crumbs" aria-label="面包屑">
          <RouterLink to="/chat" class="layout__crumb-link">首页</RouterLink>
          <span class="layout__crumb-sep">/</span>
          <span class="layout__crumb-current">{{ pageTitle }}</span>
        </nav>

        <div class="layout__topbar-right">
          <span class="layout__status" :title="statusText">
            <i class="layout__status-dot" :class="{ 'is-offline': backendOnline === false }" />
            {{ statusText }}
          </span>
          <span v-if="isChatPage && modelPill" class="layout__model">{{ modelPill }}</span>
        </div>
      </header>

      <div class="layout__content">
        <router-view />
      </div>
    </main>
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
  padding-top: 10px;
  margin-top: 8px;
  border-top: 1px solid var(--ma-color-line);
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
  background: color-mix(in srgb, var(--ma-color-ink) 4%, transparent);
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

.layout__topbar {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 32px;
  background: var(--ma-color-surface);
  border-bottom: 1px solid var(--ma-color-line);
}

.layout__crumbs {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  color: var(--ma-color-muted);
}

.layout__crumb-link {
  color: inherit;
  text-decoration: none;
}

.layout__crumb-link:hover {
  color: var(--ma-color-ink);
}

.layout__crumb-sep {
  color: var(--ma-color-faint);
}

.layout__crumb-current {
  font-weight: 600;
  color: var(--ma-color-ink);
}

.layout__topbar-right {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 12px;
  color: var(--ma-color-muted);
}

.layout__status {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.layout__status-dot {
  width: 6px;
  height: 6px;
  background: var(--ma-color-success);
  border-radius: 999px;
}

.layout__status-dot.is-offline {
  background: var(--ma-color-danger);
}

.layout__model {
  padding: 2px 10px;
  font-size: 12px;
  color: var(--ma-color-accent);
  background: var(--ma-color-accent-soft);
  border-radius: 999px;
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
