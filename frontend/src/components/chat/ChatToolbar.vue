<script setup lang="ts">
/** 对话区顶部的一行工具栏：左侧会话标题，右侧模型标签与分享。 */
import AppIcon from '@/components/ui/AppIcon.vue'
import IconButton from '@/components/ui/IconButton.vue'
import MyDropdownMenu, { type MenuItem } from '@/components/ui/MyDropdownMenu.vue'

defineProps<{
  title: string
  model: string
  /** 当前挂载的技能名；没有就是空串 */
  skillName?: string
  /** 技能菜单项：key 是 skill slug，'none' 表示卸载 */
  skillItems?: MenuItem[]
  /** 草稿态还不能挂技能（会话还没建） */
  skillDisabled?: boolean
}>()
const emit = defineEmits<{ selectSkill: [slug: string | null] }>()

function onSelectSkill(key: string) {
  emit('selectSkill', key === 'none' ? null : key)
}
</script>

<template>
  <div class="chat__bar">
    <h2 v-if="title" class="chat__title" :title="title">{{ title }}</h2>
    <span v-else class="chat__title" aria-hidden="true" />

    <div class="chat__bar-right">
      <MyDropdownMenu
        v-if="!skillDisabled || skillName"
        :items="skillItems ?? []"
        align="end"
        @select="onSelectSkill"
      >
        <!-- 触发器必须自己接 toggle：组件把开关方法作为插槽参数给出来 -->
        <template #default="{ toggle }">
          <button type="button" class="chat__skill" :class="{ 'is-on': skillName }" @click="toggle">
            <AppIcon name="sparkle" :size="14" />
            <span class="chat__skill-label">{{ skillName || '技能' }}</span>
          </button>
        </template>
      </MyDropdownMenu>
      <span v-else class="chat__skill is-off" title="先发一条消息建会话，再挂技能">
        <AppIcon name="sparkle" :size="14" />
        <span class="chat__skill-label">技能</span>
      </span>
      <span class="layout__model" :title="`当前模型：${model}`">{{ model }}</span>
      <IconButton label="分享（待实现）">
        <AppIcon name="share" :size="17" />
      </IconButton>
    </div>
  </div>
</template>

<style scoped>
.chat__bar {
  display: flex;
  flex: none;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  padding: 14px 32px 6px;
}

.chat__title {
  margin: 0;
  overflow: hidden;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.01em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat__bar-right {
  display: flex;
  flex: none;
  gap: 6px;
  align-items: center;
}

.chat__skill {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  padding: 3px 10px;
  font-size: 12px;
  color: var(--ma-color-muted);
  cursor: pointer;
  background: color-mix(in srgb, var(--ma-color-ink) 6%, transparent);
  border: 0;
  border-radius: 999px;
  transition: background-color var(--ma-motion-hover) ease;
}

.chat__skill:hover {
  background: color-mix(in srgb, var(--ma-color-ink) 10%, transparent);
}

.chat__skill.is-on {
  color: var(--ma-color-accent-ink, var(--ma-color-accent));
  background: var(--ma-color-accent-soft);
}

.chat__skill.is-off {
  opacity: 0.6;
  cursor: default;
}

.chat__skill-label {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.layout__model {
  flex: none;
  /* 工具条右边挤了三样东西，模型名不能被折成两行 */
  white-space: nowrap;
  padding: 3px 10px;
  font-size: 12px;
  color: var(--ma-color-muted);
  background: color-mix(in srgb, var(--ma-color-ink) 6%, transparent);
  border-radius: 999px;
}
</style>
