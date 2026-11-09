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
    await session.register(email.value.trim(), password.value, displayName.value.trim())
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
        <img class="auth__logo" src="/logo.png" alt="" width="28" height="28" />
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
