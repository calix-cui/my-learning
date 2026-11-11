<script setup lang="ts">
/**
 * 技能：一套可复用的「工作方法」。
 *
 * 内置技能随代码发布、只读；用户自建的存在库里，可以改和删。
 * 挂载在对话页的工具条上——这里只管「有哪些」和「怎么写」。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import AppIcon from '@/components/ui/AppIcon.vue'
import { confirmDialog } from '@/components/ui/messageBox'
import { createSkill, deleteSkill, listSkills, updateSkill } from '@/api/skills'
import { fetchToolSettings, type ToolItem } from '@/api/settings'
import type { ChatSkill, SkillPayload } from '@/types/api'

const skills = ref<ChatSkill[]>([])
const toolOptions = ref<ToolItem[]>([])
const loading = ref(false)
const saving = ref(false)
const editing = ref<number | null>(null) // null = 没在编辑；0 = 新建
const expanded = ref<string | null>(null)

const form = reactive({
  slug: '',
  name: '',
  description: '',
  instructions: '',
  tools: [] as string[],
})

const formTitle = computed(() => (editing.value === 0 ? '新建技能' : '编辑技能'))
const builtinCount = computed(() => skills.value.filter((item) => item.source === 'builtin').length)

function resetForm() {
  form.slug = ''
  form.name = ''
  form.description = ''
  form.instructions = ''
  form.tools = []
}

async function load() {
  loading.value = true
  try {
    const [list, tools] = await Promise.all([listSkills(), fetchToolSettings()])
    skills.value = list.items
    toolOptions.value = tools.items
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '读取技能失败')
  } finally {
    loading.value = false
  }
}

function startCreate() {
  resetForm()
  editing.value = 0
}

async function startEdit(skill: ChatSkill) {
  if (skill.skill_id === null) return
  resetForm()
  form.slug = skill.slug
  form.name = skill.name
  form.description = skill.description
  form.tools = [...skill.tools]
  editing.value = skill.skill_id
  // 列表里不带正文，编辑时再取一次详情
  try {
    const { getSkill } = await import('@/api/skills')
    const detail = await getSkill(skill.slug)
    form.instructions = detail.instructions
  } catch {
    ElMessage.error('正文读取失败')
  }
}

function cancelEdit() {
  editing.value = null
  resetForm()
}

function toggleTool(name: string) {
  const index = form.tools.indexOf(name)
  if (index >= 0) form.tools.splice(index, 1)
  else form.tools.push(name)
}

async function submit() {
  const payload: SkillPayload = {
    name: form.name.trim(),
    description: form.description.trim(),
    instructions: form.instructions,
    tools: [...form.tools],
  }
  saving.value = true
  try {
    if (editing.value === 0) {
      await createSkill({ ...payload, slug: form.slug.trim().toLowerCase() })
      ElMessage.success('技能已创建')
    } else if (editing.value !== null) {
      await updateSkill(editing.value, payload)
      ElMessage.success('技能已更新')
    }
    cancelEdit()
    await load()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function remove(skill: ChatSkill) {
  if (skill.skill_id === null) return
  const ok = await confirmDialog({
    title: `删除「${skill.name}」？`,
    description: '正在使用它的会话会回到「不挂技能」，对话本身不受影响。',
    confirmText: '删除',
    danger: true,
  })
  if (!ok) return
  try {
    await deleteSkill(skill.skill_id)
    ElMessage.success('已删除')
    await load()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <section class="skills">
    <header class="skills__head">
      <div>
        <h3 class="skills__title">技能</h3>
        <p class="skills__desc">
          一套可复用的工作方法：步骤、检查项、输出格式，外加该用哪些工具。挂到对话上才会生效。
        </p>
      </div>
      <button type="button" class="skills__new" @click="startCreate">
        <AppIcon name="plus" :size="15" />
        新建技能
      </button>
    </header>

    <p v-if="loading" class="skills__hint">正在读取…</p>

    <form v-else-if="editing !== null" class="skills__form" @submit.prevent="submit">
      <h4 class="skills__form-title">{{ formTitle }}</h4>
      <div class="skills__row">
        <div class="skills__field">
          <span class="skills__label">标识</span>
          <input
            v-model="form.slug"
            :disabled="editing !== 0"
            placeholder="code-review"
            aria-label="技能标识"
          />
        </div>
        <div class="skills__field">
          <span class="skills__label">名称</span>
          <input v-model="form.name" placeholder="代码审查" aria-label="技能名称" />
        </div>
      </div>
      <div class="skills__field">
        <span class="skills__label">说明</span>
        <input v-model="form.description" placeholder="一句话说清它干什么" aria-label="技能说明" />
      </div>
      <div class="skills__field">
        <span class="skills__label">正文（Markdown，会整体注入系统提示）</span>
        <textarea
          v-model="form.instructions"
          rows="8"
          placeholder="## 步骤&#10;1. …"
          aria-label="技能正文"
        />
      </div>
      <div class="skills__field">
        <span class="skills__label">工具白名单（不选 = 不限制）</span>
        <div class="skills__chips">
          <button
            v-for="tool in toolOptions"
            :key="tool.name"
            type="button"
            class="skills__chip"
            :class="{ 'is-on': form.tools.includes(tool.name) }"
            @click="toggleTool(tool.name)"
          >
            {{ tool.name }}
          </button>
          <span v-if="!toolOptions.length" class="skills__hint">还没有可用工具</span>
        </div>
      </div>
      <div class="skills__actions">
        <button type="button" class="skills__ghost" @click="cancelEdit">取消</button>
        <button type="submit" class="skills__primary" :disabled="saving">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>
    </form>

    <template v-else>
      <p class="skills__hint">
        内置 {{ builtinCount }} 个（只读），自建 {{ skills.length - builtinCount }} 个
      </p>
      <ul class="skills__list">
        <li v-for="skill in skills" :key="skill.slug" class="skills__item">
          <div class="skills__item-main">
            <div class="skills__item-head">
              <span class="skills__item-name">{{ skill.name }}</span>
              <span class="skills__tag">{{ skill.source === 'builtin' ? '内置' : '自建' }}</span>
              <span class="skills__tag skills__tag--plain">{{ skill.tool_count }} 个工具</span>
            </div>
            <p class="skills__item-desc">{{ skill.description }}</p>
            <p v-if="expanded === skill.slug" class="skills__more">
              工具：{{ skill.tools.length ? skill.tools.join('、') : '不限制' }}
            </p>
          </div>
          <div class="skills__item-actions">
            <button
              type="button"
              class="skills__mini"
              @click="expanded = expanded === skill.slug ? null : skill.slug"
            >
              {{ expanded === skill.slug ? '收起' : '详情' }}
            </button>
            <template v-if="skill.source === 'custom'">
              <button type="button" class="skills__mini" @click="startEdit(skill)">编辑</button>
              <button type="button" class="skills__mini is-danger" @click="remove(skill)">
                删除
              </button>
            </template>
          </div>
        </li>
      </ul>
    </template>
  </section>
</template>

<style scoped>
.skills {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.skills__head {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
}

.skills__head > div {
  flex: 1;
  min-width: 0;
}

.skills__title {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 600;
}

.skills__desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ma-color-muted);
}

.skills__new {
  display: inline-flex;
  flex: none;
  gap: 5px;
  align-items: center;
  padding: 8px 14px;
  font-size: 13px;
  color: var(--ma-color-on-accent);
  white-space: nowrap;
  cursor: pointer;
  background: var(--ma-color-accent);
  border: 0;
  border-radius: 999px;
}

.skills__hint {
  margin: 0;
  font-size: 12px;
  color: var(--ma-color-muted);
}

.skills__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0;
  margin: 0;
  list-style: none;
}

.skills__item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  justify-content: space-between;
  padding: 14px 16px;
  /* 用底色而不是投影分层：投影落在相邻两行之间会读成一条分割线 */
  background: var(--ma-color-canvas);
  border-radius: 16px;
}

.skills__item-main {
  flex: 1;
  min-width: 0;
}

.skills__item-head {
  display: flex;
  gap: 8px;
  align-items: center;
}

.skills__item-name {
  font-size: 14px;
  font-weight: 600;
}

.skills__tag {
  padding: 1px 8px;
  font-size: 11px;
  color: var(--ma-color-accent-ink, var(--ma-color-accent));
  background: var(--ma-color-accent-soft);
  border-radius: 999px;
}

.skills__tag--plain {
  color: var(--ma-color-muted);
  background: color-mix(in srgb, var(--ma-color-ink) 6%, transparent);
}

.skills__item-desc {
  margin: 6px 0 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--ma-color-muted);
}

.skills__more {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--ma-color-muted);
}

.skills__item-actions {
  display: flex;
  flex: none;
  gap: 4px;
  align-items: center;
}

.skills__mini {
  padding: 5px 10px;
  font-size: 12px;
  color: var(--ma-color-muted);
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: 8px;
  transition: background-color var(--ma-motion-hover) ease;
}

.skills__mini:hover {
  background: color-mix(in srgb, var(--ma-color-ink) 6%, transparent);
}

.skills__mini.is-danger {
  color: var(--ma-color-danger);
}

.skills__form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px;
  background: var(--ma-color-surface);
  border-radius: 18px;
  box-shadow: 0 1px 2px rgb(23 32 27 / 4%);
}

.skills__form-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.skills__row {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.skills__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.skills__label {
  font-size: 12px;
  color: var(--ma-color-muted);
}

.skills__field input,
.skills__field textarea {
  padding: 9px 12px;
  font: inherit;
  font-size: 13px;
  color: var(--ma-color-ink);
  background: var(--ma-color-canvas);
  border: 1px solid transparent;
  border-radius: 10px;
}

.skills__field textarea {
  line-height: 1.7;
  resize: none;
}

.skills__field input:focus,
.skills__field textarea:focus {
  background: var(--ma-color-surface);
  border-color: var(--ma-color-accent);
  outline: none;
}

.skills__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.skills__chip {
  padding: 4px 10px;
  font-size: 12px;
  color: var(--ma-color-muted);
  cursor: pointer;
  background: color-mix(in srgb, var(--ma-color-ink) 5%, transparent);
  border: 0;
  border-radius: 999px;
}

.skills__chip.is-on {
  color: var(--ma-color-accent-ink, var(--ma-color-accent));
  background: var(--ma-color-accent-soft);
}

.skills__actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.skills__ghost,
.skills__primary {
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  border: 0;
  border-radius: 999px;
}

.skills__ghost {
  color: var(--ma-color-muted);
  background: color-mix(in srgb, var(--ma-color-ink) 6%, transparent);
}

.skills__primary {
  color: var(--ma-color-on-accent);
  background: var(--ma-color-accent);
}

.skills__primary:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>
