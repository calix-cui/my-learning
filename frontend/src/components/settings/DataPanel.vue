<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { confirmDialog } from '@/components/ui/messageBox'
import { ElMessage } from 'element-plus'

import { deleteAccount } from '@/api/auth'
import { exportUrl } from '@/api/settings'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'

/**
 * 数据管理：导出全部对话（JSON / Markdown）+ 注销账号。
 *
 * 导出用 `<a download>` 交给浏览器直接下载，Cookie 会带上；
 * 注销要输入密码 + 输入「注销」确认，不可恢复。
 */
const router = useRouter()
const sessionStore = useSessionStore()
const chatStore = useChatStore()
const settingsStore = useSettingsStore()
const { conversations } = storeToRefs(chatStore)

const messageCount = computed(() =>
  conversations.value.reduce((total, item) => total + (item.message_count ?? 0), 0),
)

const password = ref('')
const confirmText = ref('')
const deleting = ref(false)

function download(format: 'json' | 'markdown') {
  const link = document.createElement('a')
  link.href = exportUrl(format)
  link.download = ''
  document.body.appendChild(link)
  link.click()
  link.remove()
}

async function handleDelete() {
  if (confirmText.value.trim() !== '注销') {
    ElMessage.warning('请先输入「注销」两个字确认')
    return
  }
  try {
    await confirmDialog({
      title: '注销后，账号将不可恢复',
      description: '账号下的会话、设置与登录设备会一起删除。',
      confirmText: '注销账号',
      danger: true,
    })
  } catch {
    return
  }
  deleting.value = true
  try {
    await deleteAccount(password.value)
    ElMessage.success('账号已注销')
    sessionStore.clear()
    chatStore.reset()
    settingsStore.reset()
    await router.push({ name: 'login' })
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <section class="data">
    <header class="data__head">
      <h2 class="data__title">数据管理</h2>
      <p class="data__desc">这里的操作只影响你自己的数据。</p>
    </header>

    <div class="data__block">
      <h3 class="data__label">导出对话</h3>
      <p class="data__hint">
        当前共 {{ conversations.length }} 个会话、{{ messageCount }} 条消息。导出的文件不包含 API
        Key 与登录凭据。
      </p>
      <div class="data__actions">
        <el-button @click="download('json')">导出 JSON</el-button>
        <el-button @click="download('markdown')">导出 Markdown</el-button>
      </div>
    </div>

    <div class="data__danger">
      <h3 class="data__danger-title">注销账号</h3>
      <p class="data__danger-desc">
        会连同 {{ conversations.length }} 个会话、{{ messageCount }}
        条消息、模型设置与登录设备一起删除。 删除后无法恢复，导出的文件请自行保存。
      </p>

      <div class="data__form">
        <el-input
          v-model="password"
          aria-label="密码"
          type="password"
          show-password
          placeholder="输入密码确认身份"
          autocomplete="current-password"
        />
        <el-input
          v-model="confirmText"
          aria-label="输入注销以确认"
          placeholder="输入「注销」以确认"
        />
      </div>

      <el-button type="danger" plain :loading="deleting" @click="handleDelete">
        永久删除我的账号
      </el-button>
    </div>
  </section>
</template>

<style scoped>
.data__head {
  margin-bottom: 20px;
}

.data__title {
  font-size: 20px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.data__desc {
  margin-top: 4px;
  font-size: 13px;
  color: var(--ma-color-muted);
}

.data__label {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.data__hint {
  font-size: 12px;
  line-height: 1.7;
  color: var(--ma-color-muted);
}

.data__actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.data__danger {
  padding: 16px;
  margin-top: 28px;
  background: var(--ma-color-danger-soft);
  border: 1px solid color-mix(in srgb, var(--ma-color-danger) 22%, transparent);
  border-radius: var(--ma-radius-md);
}

.data__danger-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ma-color-danger);
}

.data__danger-desc {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--ma-color-muted);
}

.data__form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 12px 0;
}

.data__form :deep(.el-input) {
  background: var(--ma-color-surface);
}
</style>
