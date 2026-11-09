<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ChatDotRound, Setting } from '@element-plus/icons-vue'

import { useSessionStore } from '@/stores/session'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()

/** 登录/注册页不套应用外壳（没有侧边栏和顶栏） */
const isAuthPage = computed(() => route.meta.public === true)

/** 头像里显示邮箱或显示名的首字 */
const userLabel = computed(() => session.displayName)

async function handleLogout() {
  await session.logout()
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

/** 当前高亮菜单项，与路由路径保持一致 */
const activeMenu = computed(() => route.path)

/** 当前页面标题，来自路由 meta */
const pageTitle = computed(() => (route.meta.title as string | undefined) ?? 'My Agent')

/** 后端联通状态：null 表示检测中，仅用于顶栏与侧边栏状态提示 */
const backendOnline = ref<boolean | null>(null)

onMounted(async () => {
  try {
    const response = await fetch('/healthz')
    backendOnline.value = response.ok
  } catch {
    backendOnline.value = false
  }
})

const backendStatusText = computed(() => {
  if (backendOnline.value === null) {
    return '正在检测后端'
  }
  // 容器部署时前后端同源，写死 127.0.0.1:8000 会误导，这里只报可达性
  return backendOnline.value ? '已连接后端' : '后端未连接'
})

const sidebarStatusText = computed(() => {
  if (backendOnline.value === null) {
    return '正在检测接口'
  }
  return backendOnline.value ? '接口服务正常' : '接口服务异常'
})
</script>

<template>
  <router-view v-if="isAuthPage" />
  <el-container v-else class="layout">
    <el-aside width="200px" class="layout__aside">
      <div class="layout__brand">
        <span class="layout__brand-mark">AI</span>
        <span class="layout__brand-text">My Agent</span>
      </div>

      <p class="layout__menu-label">功能菜单</p>
      <el-menu :default-active="activeMenu" router class="layout__menu">
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>对话</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>设置</span>
        </el-menu-item>
      </el-menu>

      <div class="layout__aside-footer">
        <p class="layout__version">版本 v1.0 · 2026-11</p>
        <p class="layout__status">
          <span
            class="layout__status-dot"
            :class="{ 'layout__status-dot--offline': backendOnline === false }"
          />
          {{ sidebarStatusText }}
        </p>
      </div>
    </el-aside>

    <el-container class="layout__body">
      <el-header height="56px" class="layout__topbar">
        <div class="layout__topbar-left">
          <h1 class="layout__title">{{ pageTitle }}</h1>
          <span class="layout__divider" />
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/chat' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ pageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="layout__topbar-right">
          <span class="layout__backend">
            <span
              class="layout__status-dot"
              :class="{ 'layout__status-dot--offline': backendOnline === false }"
            />
            {{ backendStatusText }}
          </span>
          <span class="layout__divider" />
          <el-dropdown trigger="click" @command="handleUserCommand">
            <span class="layout__user-trigger">
              <el-avatar :size="28" class="layout__avatar">{{ session.avatarText }}</el-avatar>
              <span class="layout__user">{{ userLabel }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>{{ session.user?.email }}</el-dropdown-item>
                <el-dropdown-item divided command="settings">设置</el-dropdown-item>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="layout__main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100%;
}

.layout__aside {
  display: flex;
  flex-direction: column;
  background-color: var(--pa-color-bg-card);
  border-right: 1px solid var(--pa-color-border);
}

.layout__brand {
  display: flex;
  flex: none;
  align-items: center;
  gap: 10px;
  height: var(--pa-topbar-height);
  padding: 0 var(--pa-space-4);
  border-bottom: 1px solid var(--pa-color-border-light);
}

.layout__brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  color: #ffffff;
  font-size: var(--pa-font-size-body);
  font-weight: 600;
  background: linear-gradient(135deg, #60a5fa, #2563eb);
  border-radius: var(--pa-radius);
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.28);
}

.layout__brand-text {
  color: var(--pa-color-text-primary);
  font-size: var(--pa-font-size-body);
  font-weight: 600;
}

.layout__menu-label {
  margin: 0;
  padding: 6px 12px;
  color: var(--pa-color-text-muted);
  font-size: var(--pa-font-size-caption);
  letter-spacing: 0.4px;
}

.layout__menu {
  flex: 1;
  padding: var(--pa-space-3);
  border-right: none;
}

.layout__menu :deep(.el-menu-item) {
  position: relative;
  height: 44px;
  margin-bottom: var(--pa-space-1);
  color: var(--pa-color-text-regular);
  border-radius: var(--pa-radius-sm);
}

.layout__menu :deep(.el-menu-item.is-active) {
  color: var(--pa-color-primary);
  font-weight: 600;
  background-color: var(--pa-color-primary-soft);
}

.layout__menu :deep(.el-menu-item.is-active)::before {
  position: absolute;
  top: 10px;
  bottom: 10px;
  left: -12px;
  width: 3px;
  background-color: var(--pa-color-primary);
  border-radius: 0 3px 3px 0;
  content: '';
}

.layout__aside-footer {
  padding: var(--pa-space-3) var(--pa-space-4);
  border-top: 1px solid var(--pa-color-border-light);
}

.layout__version,
.layout__status {
  margin: 0;
  color: var(--pa-color-text-muted);
  font-size: var(--pa-font-size-caption);
  line-height: 20px;
}

.layout__status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: var(--pa-space-1);
  color: var(--pa-color-text-secondary);
}

.layout__status-dot {
  display: inline-block;
  flex: none;
  width: 6px;
  height: 6px;
  background-color: var(--pa-color-success-500);
  border-radius: 50%;
}

.layout__status-dot--offline {
  background-color: var(--pa-color-danger);
}

.layout__body {
  min-width: 0;
}

.layout__topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--pa-space-4);
  padding: 0 var(--pa-space-6);
  background-color: var(--pa-color-bg-card);
  border-bottom: 1px solid var(--pa-color-border);
}

.layout__topbar-left,
.layout__user-trigger {
  display: inline-flex;
  align-items: center;
  gap: var(--pa-space-2);
  cursor: pointer;
}

.layout__topbar-right {
  display: flex;
  align-items: center;
  gap: var(--pa-space-3);
}

.layout__title {
  margin: 0;
  color: var(--pa-color-text-primary);
  font-size: var(--pa-font-size-title);
  font-weight: 600;
}

.layout__divider {
  width: 1px;
  height: 14px;
  background-color: var(--pa-color-border);
}

.layout__backend {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--pa-color-text-secondary);
  font-size: var(--pa-font-size-caption);
}

.layout__avatar {
  color: var(--pa-color-primary-dark);
  font-size: var(--pa-font-size-caption);
  font-weight: 600;
  background-color: var(--pa-color-primary-100);
}

.layout__user {
  color: var(--pa-color-text-regular);
  font-size: 13px;
}

.layout__main {
  padding: var(--pa-content-padding);
  overflow-y: auto;
}
</style>
