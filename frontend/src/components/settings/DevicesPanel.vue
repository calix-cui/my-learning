<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { listSessions, revokeSession } from '@/api/auth'
import type { LoginSession } from '@/types/api'

/** 登录设备：复用 /api/auth/sessions，撤销后对方下一次请求就 401 */
const sessions = ref<LoginSession[]>([])
const loading = ref(false)

async function refresh() {
  loading.value = true
  try {
    sessions.value = await listSessions()
  } finally {
    loading.value = false
  }
}

onMounted(refresh)

/** 从 UA 里挑一个可读的设备名，识别不了就原样显示 */
function deviceName(ua: string | null): string {
  if (!ua) return '未知设备'
  const browser = /Edg\//.test(ua)
    ? 'Edge'
    : /Chrome\//.test(ua)
      ? 'Chrome'
      : /Safari\//.test(ua) && !/Chrome\//.test(ua)
        ? 'Safari'
        : /Firefox\//.test(ua)
          ? 'Firefox'
          : '浏览器'
  const system = /Mac OS X/.test(ua)
    ? 'macOS'
    : /Windows/.test(ua)
      ? 'Windows'
      : /Linux/.test(ua)
        ? 'Linux'
        : /iPhone|iPad/.test(ua)
          ? 'iOS'
          : ''
  return system ? `${browser} · ${system}` : browser
}

async function handleRevoke(item: LoginSession) {
  try {
    await ElMessageBox.confirm(
      `撤销后，「${deviceName(item.user_agent)}」需要重新登录。`,
      '撤销这台设备？',
      { confirmButtonText: '撤销', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  await revokeSession(item.id)
  ElMessage.success('已撤销该设备')
  await refresh()
}
</script>

<template>
  <section class="devices">
    <header class="devices__head">
      <h2 class="devices__title">登录设备</h2>
      <p class="devices__desc">
        当前账号的登录会话。撤销后对方下一次请求就会退出，不影响你正在用的这台。
      </p>
    </header>

    <ul v-loading="loading" class="devices__list">
      <li v-for="item in sessions" :key="item.id" class="devices__item">
        <div class="devices__meta">
          <span class="devices__name">
            {{ deviceName(item.user_agent) }}
            <span v-if="item.is_current" class="devices__badge">当前设备</span>
          </span>
          <span class="devices__sub">
            {{ item.ip || '未知 IP' }} · 最近活跃 {{ item.last_seen_time }} · 到期
            {{ item.expires_time }}
          </span>
        </div>
        <el-button v-if="!item.is_current" link type="danger" @click="handleRevoke(item)">
          撤销
        </el-button>
      </li>
      <li v-if="!loading && sessions.length === 0" class="devices__empty">没有其他登录设备。</li>
    </ul>

    <p class="devices__hint">会话默认 30 天，使用中会滑动续期；改密码会一次性撤销其他所有设备。</p>
  </section>
</template>

<style scoped>
.devices__head {
  margin-bottom: 20px;
}

.devices__title {
  font-size: 20px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.devices__desc {
  margin-top: 4px;
  font-size: 13px;
  color: var(--ma-color-muted);
}

.devices__list {
  border: 1px solid var(--ma-color-line);
  border-radius: var(--ma-radius-md);
  background: var(--ma-color-surface);
}

.devices__item {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
}

.devices__item + .devices__item {
  border-top: 1px solid var(--ma-color-line);
}

.devices__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.devices__name {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.devices__badge {
  padding: 1px 6px;
  font-size: 11px;
  font-weight: 400;
  color: var(--ma-color-accent);
  background: var(--ma-color-accent-soft);
  border-radius: 999px;
}

.devices__sub {
  font-size: 12px;
  color: var(--ma-color-muted);
}

.devices__empty {
  padding: 16px;
  font-size: 13px;
  color: var(--ma-color-muted);
}

.devices__hint {
  margin-top: 12px;
  font-size: 12px;
  color: var(--ma-color-muted);
}
</style>
