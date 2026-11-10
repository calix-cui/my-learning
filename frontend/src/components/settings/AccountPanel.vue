<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'

import { changePassword, updateProfile } from '@/api/auth'
import { useSessionStore } from '@/stores/session'

/** 账号资料：显示名可改、邮箱只读、改密码会踢掉其他设备 */
const sessionStore = useSessionStore()
const { user } = storeToRefs(sessionStore)

const displayName = ref(user.value?.display_name ?? '')
const savingName = ref(false)

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const savingPassword = ref(false)

const email = computed(() => user.value?.email ?? '')

async function saveName() {
  if (!user.value) return
  savingName.value = true
  try {
    user.value = await updateProfile(displayName.value.trim())
    ElMessage.success('显示名已更新')
  } finally {
    savingName.value = false
  }
}

async function savePassword() {
  if (newPassword.value.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  savingPassword.value = true
  try {
    await changePassword(oldPassword.value, newPassword.value)
    oldPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    ElMessage.success('密码已更新，其他设备需要重新登录')
  } finally {
    savingPassword.value = false
  }
}
</script>

<template>
  <section class="account">
    <header class="account__head">
      <h2 class="account__title">账号资料</h2>
      <p class="account__desc">邮箱是登录标识，暂时不支持修改。</p>
    </header>

    <div class="account__block">
      <span class="account__label">邮箱</span>
      <el-input :model-value="email" aria-label="邮箱" readonly />
    </div>

    <div class="account__block">
      <span class="account__label">显示名</span>
      <div class="account__row">
        <el-input
          v-model="displayName"
          aria-label="显示名"
          maxlength="50"
          placeholder="留空则显示邮箱"
        />
        <el-button :loading="savingName" @click="saveName">保存</el-button>
      </div>
      <p class="account__hint">显示在左下角与助手称呼里，最多 50 个字。</p>
    </div>

    <div class="account__block">
      <h3 class="account__label">修改密码</h3>
      <div class="account__form">
        <el-input
          v-model="oldPassword"
          aria-label="当前密码"
          type="password"
          show-password
          placeholder="当前密码"
          autocomplete="current-password"
        />
        <el-input
          v-model="newPassword"
          aria-label="新密码"
          type="password"
          show-password
          placeholder="新密码（至少 8 位）"
          autocomplete="new-password"
        />
        <el-input
          v-model="confirmPassword"
          aria-label="确认新密码"
          type="password"
          show-password
          placeholder="再输一次新密码"
          autocomplete="new-password"
        />
      </div>
      <div class="account__actions">
        <el-button type="primary" :loading="savingPassword" @click="savePassword">
          更新密码
        </el-button>
      </div>
      <p class="account__hint">改完密码后，其他设备上的登录会立即失效。</p>
    </div>
  </section>
</template>

<style scoped>
.account__head {
  margin-bottom: 20px;
}

.account__title {
  font-size: 20px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.account__desc {
  margin-top: 4px;
  font-size: 13px;
  color: var(--ma-color-muted);
}

.account__block + .account__block {
  margin-top: 20px;
}

.account__label {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.account__row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.account__row :deep(.el-input) {
  flex: 1;
}

.account__form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.account__actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.account__hint {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--ma-color-muted);
}
</style>
