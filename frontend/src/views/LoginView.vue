<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useSessionStore } from '@/stores/session'

const router = useRouter()
const route = useRoute()
const session = useSessionStore()

const email = ref('')
const password = ref('')
const submitting = ref(false)

/** 登录后回跳到被拦截的页面（守卫写在 query.redirect） */
const redirect = computed(() => {
  const target = route.query.redirect
  return typeof target === 'string' && target.startsWith('/') ? target : '/chat'
})

async function handleSubmit() {
  if (!email.value.trim() || !password.value) {
    ElMessage.warning('请填写邮箱和密码')
    return
  }
  submitting.value = true
  try {
    await session.login(email.value.trim(), password.value)
    ElMessage.success('登录成功')
    await router.replace(redirect.value)
  } catch {
    // 错误提示由 axios 拦截器统一弹出，这里只恢复按钮状态
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth">
    <div class="auth__card">
      <div class="auth__brand">
        <span class="auth__mark">AI</span>
        <span class="auth__name">My Agent</span>
      </div>

      <h1 class="auth__title">登录</h1>
      <p class="auth__subtitle">登录后即可与你的助手对话，历史会话只属于你。</p>

      <el-form label-position="top" @submit.prevent="handleSubmit">
        <el-form-item label="邮箱">
          <el-input
            v-model="email"
            type="email"
            autocomplete="username"
            placeholder="you@example.com"
            size="large"
            @keyup.enter="handleSubmit"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="password"
            type="password"
            show-password
            autocomplete="current-password"
            placeholder="至少 8 位"
            size="large"
            @keyup.enter="handleSubmit"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          class="auth__submit"
          :loading="submitting"
          @click="handleSubmit"
        >
          登录
        </el-button>
      </el-form>

      <p class="auth__switch">
        还没有账号？
        <router-link to="/register">注册一个</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 32px 16px;
  background: linear-gradient(160deg, #eef2ff 0%, #f8fafc 55%, #f1f5f9 100%);
}

.auth__card {
  width: 100%;
  max-width: 400px;
  padding: 32px;
  background-color: #ffffff;
  border: 1px solid var(--pa-color-border);
  border-radius: var(--pa-radius-lg);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
}

.auth__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 24px;
}

.auth__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
  background: linear-gradient(135deg, #60a5fa, #2563eb);
  border-radius: var(--pa-radius);
}

.auth__name {
  color: var(--pa-color-text-primary);
  font-size: 16px;
  font-weight: 600;
}

.auth__title {
  margin: 0 0 6px;
  color: var(--pa-color-text-primary);
  font-size: 22px;
  line-height: 30px;
}

.auth__subtitle {
  margin: 0 0 24px;
  color: var(--pa-color-text-muted);
  font-size: 13px;
  line-height: 20px;
}

.auth__submit {
  width: 100%;
  margin-top: 4px;
}

.auth__switch {
  margin: 20px 0 0;
  color: var(--pa-color-text-muted);
  font-size: 13px;
  text-align: center;
}

.auth__switch a {
  color: var(--pa-color-primary);
  font-weight: 600;
  text-decoration: none;
}
</style>
