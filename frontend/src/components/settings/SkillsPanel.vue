<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getSkill } from '@/api/skills'
import { useSkillsStore } from '@/stores/skills'
import { useSessionStore } from '@/stores/session'
import MarkdownContent from '@/components/chat/MarkdownContent.vue'
import type { LocalSkill } from '@/types/api'

const catalog = useSkillsStore()
const session = useSessionStore()
const expanded = ref<string | null>(null)
const instructions = ref('')
const detailError = ref('')
const detailLoading = ref(false)
let detailRequest = 0

async function refresh() {
  detailRequest++
  expanded.value = null
  instructions.value = ''
  await catalog.scan()
}

async function openDetail(skill: LocalSkill) {
  if (expanded.value === skill.key) {
    expanded.value = null
    detailRequest++
    return
  }
  expanded.value = skill.key
  instructions.value = ''
  detailError.value = ''
  detailLoading.value = true
  const request = ++detailRequest
  try {
    const detail = await getSkill(skill.key, catalog.version)
    if (request === detailRequest) instructions.value = detail.instructions
  } catch {
    if (request === detailRequest) detailError.value = '读取失败，请重新扫描后重试'
  } finally {
    if (request === detailRequest) detailLoading.value = false
  }
}

onMounted(() => {
  if (catalog.accountId === session.user?.id) {
    void catalog.scan()
  } else {
    void catalog.initialize(session.user?.id ?? null)
  }
})
</script>

<template>
  <section class="skills">
    <header class="skills__head">
      <h3>Skill</h3>
      <button
        type="button"
        class="skills__action u-tint"
        :disabled="catalog.loading"
        @click="refresh"
      >
        {{ catalog.loading ? '正在扫描…' : '重新扫描' }}
      </button>
    </header>

    <p class="skills__hint">从后端配置的本地目录发现。安装或更新 SKILL.md 后，重新扫描即可使用。</p>
    <p v-if="catalog.error" role="alert">{{ catalog.error }}</p>
    <p v-else-if="!catalog.loading && !catalog.items.length" class="skills__hint">尚未发现 Skill</p>

    <div v-for="skill in catalog.items" :key="skill.key" class="skills__item">
      <div class="skills__head">
        <div>
          <h4>{{ skill.name }}</h4>
          <p class="skills__hint">{{ skill.key }}</p>
        </div>
        <button
          type="button"
          class="skills__action u-tint"
          :aria-expanded="expanded === skill.key"
          :disabled="catalog.loading"
          @click="openDetail(skill)"
        >
          {{ expanded === skill.key ? '收起说明' : '查看说明' }}
        </button>
      </div>
      <p>{{ skill.description }}</p>
      <template v-if="expanded === skill.key">
        <p v-if="detailLoading" role="status">正在读取…</p>
        <p v-else-if="detailError" role="alert">{{ detailError }}</p>
        <MarkdownContent v-else :content="instructions" />
      </template>
    </div>

  </section>
</template>

<style scoped>
.skills,
.skills__item {
  display: flex;
  flex-direction: column;
  gap: var(--ma-space-sm);
}

.skills {
  gap: var(--ma-space-md);
}

.skills h3,
.skills h4,
.skills p {
  margin: 0;
}

.skills__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ma-space-sm);
}

.skills__hint {
  color: var(--ma-color-muted);
  overflow-wrap: anywhere;
}

.skills__item {
  padding: var(--ma-space-md);
  background: var(--ma-color-canvas);
  border-radius: var(--ma-radius-md);
}

.skills__action {
  flex-shrink: 0;
  padding: var(--ma-space-xs) var(--ma-space-sm);
  font: inherit;
  color: var(--ma-color-accent);
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: var(--ma-radius-sm);
}

.skills__action:disabled {
  color: var(--ma-color-faint);
  cursor: default;
}
</style>
