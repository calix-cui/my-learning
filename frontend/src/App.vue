<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import AsideView from '@/components/layout/AsideView.vue'
import SettingsDialog from '@/components/settings/SettingsDialog.vue'
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

async function openSettings() {
  settingsOpen.value = true
  await router.replace({ path: '/chat', query: { settings: '1' } })
}
</script>

<template>
  <MyMessageBox />

  <router-view v-if="isAuthPage" />

  <!-- 等路由与会话都就绪再挂外壳：未登录时挂出侧栏会先发一次 401 请求 -->
  <div v-else-if="session.loaded && session.isLoggedIn" class="layout">
    <AsideView @settings="openSettings" @logout="handleLogout" />

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
</style>
