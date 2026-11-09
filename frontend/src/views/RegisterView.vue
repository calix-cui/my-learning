<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { register } from '@/stores/session'

const router = useRouter()
const route = useRoute()

const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const displayName = ref('')
const submitting = ref(false)

/** 注册成功后回跳到被拦截的页面 */
const redirect = computed(() => {
  const target = route.query.redirect
  return typeof target === 'string' && target.startsWith('/') ? target : '/chat'
})

async function handleSubmit() {
  if (!email.value.trim() || !password.value) {
    ElMessage.warning('请填写邮箱和密码')
    return
  }
  if (password.value.length < 8) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  if (password.value !== confirmPassword.value) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  submitting.value = true
  try {
    await register(email.value.trim(), password.value, displayName.value.trim())
    ElMessage.success('注册成功，已自动登录')
    await router.replace(redirect.value)
  } catch {
    // 错误提示由 axios 拦截器统一弹出
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

      <h1 class="auth__title">注册</h1>
      <p class="auth__subtitle">创建账号后即可开始对话，会话与记忆只属于你自己。</p>

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
            autocomplete="new-password"
            placeholder="至少 8 位"
            size="large"
            @keyup.enter="handleSubmit"
          />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input
            v-model="confirmPassword"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="再输入一次"
            size="large"
            @keyup.enter="handleSubmit"
          />
        </el-form-item>
        <el-form-item label="显示名称（可选）">
          <el-input
            v-model="displayName"
            placeholder="别人怎么称呼你"
            size="large"
            maxlength="50"
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
          注册并登录
        </el-button>
      </el-form>

      <p class="auth__switch">
        已经有账号了？
        <router-link to="/login">去登录</router-link>
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
  margin-bottom: 20px;
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
  margin: 0 0 20px;
  color: var(--pa-color-text-muted);
  font-size: 13px;
  line-height: 20px;
}

.auth__submit {
  width: 100%;
  margin-top: 4px;
}

.auth__switch {
  margin: 18px 0 0;
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
