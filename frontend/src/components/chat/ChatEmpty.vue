<script setup lang="ts">
/** 还没开始对话时的首屏：一个 logo、一句招呼。不再堆说明文字。 */
</script>

<template>
  <div class="chat__empty">
    <img class="chat__empty-logo" src="/logo.png" alt="" width="48" height="48" />
    <p class="chat__empty-title">你好，让我们开始聊天吧</p>
  </div>
</template>

<style scoped>
.chat__empty {
  display: flex;
  flex-direction: column;
  gap: 14px;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding-bottom: 8vh;
}

.chat__empty-logo {
  border-radius: 14px;
}

.chat__empty-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--ma-color-ink);
}
</style>
