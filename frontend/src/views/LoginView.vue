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
        <img class="auth__logo" src="/logo.png" alt="" width="28" height="28" />
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
