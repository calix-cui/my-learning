<script setup lang="ts">
/**
 * 工具市场：把「接入一台 MCP 服务器」做成挑卡片。
 *
 * 交互上刻意不做弹窗：需要路径的条目、自定义条目都在页面内就地展开。
 * 原因是设置本身已经是一层浮层，再叠一层弹窗既要点两次遮罩，E2E 也容易点错元素。
 *
 * 状态文案只有三种：未连接（还没试过）、正常、失败——失败的卡片展开后能看到原因。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import AppIcon from '@/components/ui/AppIcon.vue'
import { toIconName } from '@/components/ui/icon-paths'
import { confirmDialog } from '@/components/ui/messageBox'
import {
  createServer,
  deleteServer,
  fetchCatalog,
  fetchServers,
  testServer,
  updateServer,
} from '@/api/mcp'
import type { McpCatalogItem, McpCreatePayload, McpServer, McpServerStatus } from '@/types/api'

type Filter = 'all' | 'installed' | 'local' | 'remote'

const catalog = ref<McpCatalogItem[]>([])
const servers = ref<McpServer[]>([])
const loading = ref(false)
const busy = ref<string | null>(null)
const filter = ref<Filter>('all')

/** 展开工具清单的服务器 id */
const expanded = ref<Set<number>>(new Set())

function toggleTools(id: number) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}

/**
 * 点「N 个工具」：清单在缓存里就直接展开；
 * 后端重启后连接池是冷的，这时先试连一次把 tools 拉回来再展开。
 */
async function openTools(row: McpServer) {
  if (row.tools?.length) {
    toggleTools(row.id)
    return
  }
  if (!row.enabled) return
  busy.value = row.slug
  try {
    // 「试连」不进连接池缓存，清单直接从返回值里拿，别再请求一次列表
    const result = await testServer(row.id)
    if (!result.ok) {
      ElMessage.error(result.message)
      return
    }
    servers.value = servers.value.map((item) =>
      item.id === row.id
        ? { ...item, tools: result.tools, tool_count: result.tools.length, last_status: 'ok' }
        : item,
    )
    expanded.value = new Set([...expanded.value, row.id])
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '读取工具清单失败')
  } finally {
    busy.value = null
  }
}

/** 需要路径的条目：先问目录，再接入 */
const pathTarget = ref<McpCatalogItem | null>(null)
const pathValue = ref('')

/** 自定义条目表单 */
const customOpen = ref(false)
const custom = ref({
  slug: '',
  display_name: '',
  transport: 'stdio' as 'stdio' | 'http',
  command: 'uvx',
  args: '',
  url: '',
  env: '',
})

const STATUS_TEXT: Record<McpServerStatus, string> = {
  unknown: '未连接',
  ok: '正常',
  error: '失败',
}

const bySlug = computed(() => new Map(servers.value.map((row) => [row.slug, row])))

/** 自定义接入的服务器不在市场清单里，单独补卡片 */
const customServers = computed(() =>
  servers.value.filter((row) => !catalog.value.some((item) => item.slug === row.slug)),
)

const filters: { key: Filter; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'installed', label: '已接入' },
  { key: 'local', label: '本地' },
  { key: 'remote', label: '远程' },
]

const visible = computed(() =>
  catalog.value.filter((item) => {
    if (filter.value === 'installed') return Boolean(bySlug.value.get(item.slug))
    if (filter.value === 'local') return item.transport === 'stdio'
    if (filter.value === 'remote') return item.transport === 'http'
    return true
  }),
)

function serverOf(slug: string): McpServer | undefined {
  return bySlug.value.get(slug)
}

async function load() {
  loading.value = true
  try {
    const [list, mine] = await Promise.all([fetchCatalog(), fetchServers()])
    catalog.value = list.items
    servers.value = mine.items
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '读取工具市场失败')
  } finally {
    loading.value = false
  }
}

function startInstall(item: McpCatalogItem) {
  if (item.requires_path) {
    pathTarget.value = item
    pathValue.value = ''
    return
  }
  void install({ slug: item.slug })
}

async function install(payload: McpCreatePayload) {
  busy.value = payload.slug
  try {
    const row = await createServer(payload)
    servers.value = [row, ...servers.value.filter((item) => item.id !== row.id)]
    pathTarget.value = null
    pathValue.value = ''
    customOpen.value = false
    ElMessage.success(`已接入 ${row.display_name}`)
    // 接入后立刻试连一次：用户马上能看到「正常 / 失败」而不是「未连接」
    void runTest(row)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '接入失败')
  } finally {
    busy.value = null
  }
}

function confirmPath() {
  const target = pathTarget.value
  if (!target) return
  if (!pathValue.value.trim()) {
    ElMessage.warning('先填一个目录或文件路径')
    return
  }
  void install({ slug: target.slug, path: pathValue.value.trim() })
}

async function toggle(row: McpServer, enabled: boolean) {
  const previous = row.enabled
  row.enabled = enabled
  busy.value = row.slug
  try {
    const next = await updateServer(row.id, { enabled })
    servers.value = servers.value.map((item) => (item.id === next.id ? next : item))
  } catch (error) {
    row.enabled = previous
    ElMessage.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    busy.value = null
  }
}

async function runTest(row: McpServer) {
  busy.value = row.slug
  try {
    const result = await testServer(row.id)
    if (result.ok) {
      ElMessage.success(result.message)
    } else {
      ElMessage.error(result.message)
    }
    servers.value = await fetchServers().then((data) => data.items)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '测试连接失败')
  } finally {
    busy.value = null
  }
}

async function remove(row: McpServer) {
  const ok = await confirmDialog({
    title: `移除 ${row.display_name}？`,
    description: '移除后它的工具会立刻从模型可用列表里消失，历史对话不受影响。',
    confirmText: '移除',
    danger: true,
  })
  if (!ok) return
  busy.value = row.slug
  try {
    await deleteServer(row.id)
    servers.value = servers.value.filter((item) => item.id !== row.id)
    ElMessage.success('已移除')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '移除失败')
  } finally {
    busy.value = null
  }
}

function parseEnv(raw: string): Record<string, string> {
  const env: Record<string, string> = {}
  for (const line of raw.split('\n')) {
    const text = line.trim()
    if (!text) continue
    const at = text.indexOf('=')
    if (at <= 0) continue
    env[text.slice(0, at).trim()] = text.slice(at + 1).trim()
  }
  return env
}

function submitCustom() {
  const slug = custom.value.slug.trim()
  if (!/^[a-z0-9][a-z0-9-]{0,31}$/.test(slug)) {
    ElMessage.warning('标识只能用 1–32 位小写字母、数字与连字符')
    return
  }
  const payload: McpCreatePayload = {
    slug,
    display_name: custom.value.display_name.trim() || slug,
    transport: custom.value.transport,
  }
  const env = parseEnv(custom.value.env)
  if (Object.keys(env).length) payload.env = env
  if (custom.value.transport === 'stdio') {
    payload.command = custom.value.command.trim()
    payload.args = custom.value.args.trim() ? custom.value.args.trim().split(/\s+/) : []
  } else {
    payload.url = custom.value.url.trim()
  }
  void install(payload)
}

onMounted(load)
</script>

<template>
  <section v-loading="loading" class="market">
    <header class="market__head">
      <div>
        <h2 class="market__title">工具市场</h2>
        <p class="market__desc">
          接入 MCP 服务器，把它的工具借给助手用。外部工具每次调用前都会先问你。
        </p>
      </div>
      <button class="market__custom" @click="customOpen = !customOpen">
        <AppIcon name="plus" :size="16" />
        <span>自定义接入</span>
      </button>
    </header>

    <div class="market__chips" role="tablist" aria-label="筛选工具">
      <button
        v-for="item in filters"
        :key="item.key"
        class="market__chip u-tint"
        :class="{ 'is-active': filter === item.key }"
        role="tab"
        :aria-selected="filter === item.key"
        @click="filter = item.key"
      >
        {{ item.label }}
      </button>
    </div>

    <form v-if="customOpen" class="market__form" @submit.prevent="submitCustom">
      <h3 class="market__form-title">自定义接入</h3>
      <div class="market__form-grid">
        <div class="market__field">
          <span class="market__field-label">标识</span>
          <input
            id="mcp-slug"
            aria-label="标识"
            v-model="custom.slug"
            placeholder="my-server"
            maxlength="32"
          />
        </div>
        <div class="market__field">
          <span class="market__field-label">显示名</span>
          <input
            id="mcp-display-name"
            aria-label="显示名"
            v-model="custom.display_name"
            placeholder="我的工具"
            maxlength="64"
          />
        </div>
        <div class="market__field">
          <span class="market__field-label">传输</span>
          <select id="mcp-transport" aria-label="传输" v-model="custom.transport">
            <option value="stdio">本地命令（stdio）</option>
            <option value="http">远程地址（https）</option>
          </select>
        </div>
        <template v-if="custom.transport === 'stdio'">
          <div class="market__field">
            <span class="market__field-label">启动命令</span>
            <input
              id="mcp-command"
              aria-label="启动命令"
              v-model="custom.command"
              placeholder="uvx / npx / python"
            />
          </div>
          <div class="market__field market__field--wide">
            <span class="market__field-label">参数</span>
            <input
              id="mcp-args"
              aria-label="参数"
              v-model="custom.args"
              placeholder="mcp-server-fetch"
            />
          </div>
        </template>
        <div v-else class="market__field market__field--wide">
          <span class="market__field-label">服务器 URL</span>
          <input
            id="mcp-url"
            aria-label="服务器 URL"
            v-model="custom.url"
            placeholder="https://example.com/mcp"
          />
        </div>
        <div class="market__field market__field--wide">
          <span class="market__field-label">环境变量（每行 KEY=VALUE，加密保存）</span>
          <textarea
            id="mcp-env"
            aria-label="环境变量"
            v-model="custom.env"
            rows="2"
            placeholder="TOKEN=xxx"
          />
        </div>
      </div>
      <div class="market__form-actions">
        <button type="button" class="market__ghost" @click="customOpen = false">取消</button>
        <button type="submit" class="market__cta" :disabled="busy === custom.slug.trim()">
          接入
        </button>
      </div>
    </form>

    <form v-if="pathTarget" class="market__path" @submit.prevent="confirmPath">
      <AppIcon :name="toIconName(pathTarget.icon)" :size="20" />
      <div class="market__path-main">
        <strong>{{ pathTarget.display_name }}</strong>
        <span>{{ pathTarget.summary }}</span>
      </div>
      <input v-model="pathValue" class="market__path-input" placeholder="/Users/me/repo" />
      <button type="button" class="market__ghost" @click="pathTarget = null">取消</button>
      <button type="submit" class="market__cta">接入</button>
    </form>

    <div class="market__grid">
      <article
        v-for="item in visible"
        :key="item.slug"
        class="market__card u-tint"
        :class="{ 'is-installed': serverOf(item.slug) }"
      >
        <div class="market__card-top">
          <span class="market__icon">
            <AppIcon :name="toIconName(item.icon)" :size="22" />
          </span>
          <div class="market__card-heading">
            <h3 class="market__name">{{ item.display_name }}</h3>
            <div class="market__tags">
              <span v-for="tag in item.tags" :key="tag" class="market__tag">{{ tag }}</span>
            </div>
          </div>
        </div>

        <p class="market__summary">{{ item.summary }}</p>

        <p v-if="serverOf(item.slug)?.last_status === 'error'" class="market__error">
          {{ serverOf(item.slug)?.last_error || '连接失败' }}
        </p>

        <footer class="market__card-foot">
          <template v-if="serverOf(item.slug)">
            <span class="market__status" :class="`is-${serverOf(item.slug)?.last_status}`">
              {{ STATUS_TEXT[serverOf(item.slug)!.last_status] }}
            </span>
            <button
              class="market__count market__count--link"
              :disabled="!(serverOf(item.slug)!.tool_count > 0)"
              @click="openTools(serverOf(item.slug)!)"
            >
              {{ serverOf(item.slug)?.tool_count ?? 0 }} 个工具
            </button>
            <span class="market__actions">
              <el-switch
                :model-value="serverOf(item.slug)!.enabled"
                :aria-label="`启用 ${item.display_name}`"
                @update:model-value="toggle(serverOf(item.slug)!, Boolean($event))"
              />
              <button
                class="market__mini"
                :disabled="busy === item.slug"
                @click="runTest(serverOf(item.slug)!)"
              >
                {{ busy === item.slug ? '测试中…' : '试连' }}
              </button>
              <button class="market__mini is-danger" @click="remove(serverOf(item.slug)!)">
                移除
              </button>
            </span>
          </template>
          <template v-else>
            <span class="market__spacer" />
            <button class="market__cta" :disabled="busy === item.slug" @click="startInstall(item)">
              {{ busy === item.slug ? '接入中…' : '接入' }}
            </button>
          </template>
        </footer>
        <ul
          v-if="serverOf(item.slug) && expanded.has(serverOf(item.slug)!.id)"
          class="market__tools"
        >
          <li v-for="tool in serverOf(item.slug)!.tools" :key="tool.name" class="market__tool">
            <span class="market__tool-name">{{ tool.name }}</span>
            <span class="market__tool-desc">{{ tool.description }}</span>
          </li>
        </ul>
      </article>

      <article
        v-for="row in customServers"
        :key="`custom-${row.id}`"
        class="market__card u-tint is-installed"
      >
        <div class="market__card-top">
          <span class="market__icon"><AppIcon name="sparkle" :size="22" /></span>
          <div class="market__card-heading">
            <h3 class="market__name">{{ row.display_name }}</h3>
            <div class="market__tags"><span class="market__tag">自定义</span></div>
          </div>
        </div>
        <p class="market__summary">
          {{
            row.transport === 'http'
              ? row.url
              : [row.command, ...row.args].filter(Boolean).join(' ')
          }}
        </p>
        <p v-if="row.last_status === 'error'" class="market__error">
          {{ row.last_error || '连接失败' }}
        </p>
        <footer class="market__card-foot">
          <span class="market__status" :class="`is-${row.last_status}`">
            {{ STATUS_TEXT[row.last_status] }}
          </span>
          <button
            class="market__count market__count--link"
            :disabled="!(row.tool_count > 0)"
            @click="openTools(row)"
          >
            {{ row.tool_count }} 个工具
          </button>
          <span class="market__actions">
            <el-switch
              :model-value="row.enabled"
              :aria-label="`启用 ${row.display_name}`"
              @update:model-value="toggle(row, Boolean($event))"
            />
            <button class="market__mini" :disabled="busy === row.slug" @click="runTest(row)">
              {{ busy === row.slug ? '测试中…' : '试连' }}
            </button>
            <button class="market__mini is-danger" @click="remove(row)">移除</button>
          </span>
        </footer>
        <ul v-if="expanded.has(row.id)" class="market__tools">
          <li v-for="tool in row.tools" :key="tool.name" class="market__tool">
            <span class="market__tool-name">{{ tool.name }}</span>
            <span class="market__tool-desc">{{ tool.description }}</span>
          </li>
        </ul>
      </article>
    </div>

    <div v-if="!visible.length && !customServers.length && !loading" class="market__empty">
      <AppIcon name="sparkle" :size="18" />
      <span>这个筛选下还没有条目</span>
    </div>
  </section>
</template>

<style scoped>
.market {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.market__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.market__head > div {
  flex: 1;
  min-width: 0;
}

.market__title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.market__desc {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--ma-color-ink-muted);
}

.market__custom,
.market__ghost,
.market__cta,
.market__mini {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 14px;
  font-size: 13px;
  cursor: pointer;
  border: 0;
  border-radius: 10px;
  transition:
    color var(--ma-motion-hover) ease,
    background-color var(--ma-motion-hover) ease;
}

.market__custom {
  flex: none;
  white-space: nowrap;
  color: var(--ma-color-ink);
  background: var(--ma-color-surface);
  box-shadow: var(--ma-shadow-soft, 0 1px 2px rgb(0 0 0 / 6%));
}

.market__custom:hover {
  background: var(--ma-color-canvas);
}

.market__ghost {
  color: var(--ma-color-ink-muted);
  background: transparent;
}

.market__ghost:hover {
  color: var(--ma-color-ink);
  background: var(--ma-color-canvas);
}

.market__cta {
  color: var(--ma-color-on-accent);
  background: var(--ma-color-accent);
}

.market__cta:hover {
  filter: brightness(1.05);
}

.market__cta:disabled,
.market__mini:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.market__mini {
  height: 28px;
  padding: 0 10px;
  font-size: 12px;
  color: var(--ma-color-ink-muted);
  background: transparent;
}

.market__mini:hover {
  color: var(--ma-color-ink);
  background: var(--ma-color-canvas);
}

.market__mini.is-danger:hover {
  color: var(--ma-color-danger, #b3261e);
}

.market__chips {
  display: flex;
  gap: 8px;
}

.market__chip {
  height: 30px;
  padding: 0 14px;
  font-size: 13px;
  color: var(--ma-color-ink-muted);
  cursor: pointer;
  background: var(--ma-color-canvas);
  border: 0;
  border-radius: 999px;
}

.market__chip.is-active {
  color: var(--ma-color-accent-ink);
  background: var(--ma-color-accent-soft);
}

.market__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  align-items: start;
  gap: 16px;
}

.market__card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px;
  background: var(--ma-color-surface);
  border: 1px solid transparent;
  border-radius: 18px;
  box-shadow: 0 1px 2px rgb(23 32 27 / 4%);
}

.market__card.is-installed {
  border-color: var(--ma-color-accent-soft);
}

.market__card-top {
  display: flex;
  align-items: center;
  gap: 12px;
}

.market__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  color: var(--ma-color-accent-ink);
  background: var(--ma-color-accent-soft);
  border-radius: 14px;
}

.market__card-heading {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.market__name {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.market__tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.market__tag {
  padding: 1px 8px;
  font-size: 11px;
  color: var(--ma-color-ink-muted);
  background: var(--ma-color-canvas);
  border-radius: 999px;
}

.market__summary {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--ma-color-ink-muted);
}

.market__error {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--ma-color-danger, #b3261e);
}

.market__card-foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: auto;
  padding-top: 4px;
}

.market__actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  white-space: nowrap;
}

.market__spacer {
  flex: 1;
}

.market__status {
  padding: 1px 8px;
  font-size: 11px;
  white-space: nowrap;
  border-radius: 999px;
}

.market__status.is-unknown {
  color: var(--ma-color-ink-muted);
  background: var(--ma-color-canvas);
}

.market__status.is-ok {
  color: var(--ma-color-success-ink, var(--ma-color-accent-ink));
  background: var(--ma-color-success-soft, var(--ma-color-accent-soft));
}

.market__status.is-error {
  color: var(--ma-color-danger, #b3261e);
  background: color-mix(in srgb, var(--ma-color-danger, #b3261e) 12%, transparent);
}

.market__count {
  padding: 0;
  font-size: 12px;
  color: var(--ma-color-ink-muted);
  background: none;
  border: 0;
}

.market__count--link {
  cursor: pointer;
  text-decoration: underline;
  text-decoration-color: color-mix(in srgb, var(--ma-color-ink-muted) 40%, transparent);
  text-underline-offset: 3px;
}

.market__count--link:disabled {
  cursor: default;
  text-decoration: none;
}

.market__tools {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0;
  padding: 10px 12px;
  list-style: none;
  background: var(--ma-color-canvas);
  border-radius: 10px;
}

.market__tool {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.market__tool-name {
  font-family: var(--ma-font-mono);
  font-size: 12px;
  color: var(--ma-color-ink);
}

.market__tool-desc {
  font-size: 12px;
  line-height: 1.5;
  color: var(--ma-color-ink-muted);
}

.market__form,
.market__path {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 18px;
  background: var(--ma-color-surface);
  border-radius: 18px;
  box-shadow: 0 1px 2px rgb(23 32 27 / 4%);
}

.market__path {
  align-items: center;
}

.market__path-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 13px;
  color: var(--ma-color-ink-muted);
}

.market__path-main strong {
  font-size: 14px;
  color: var(--ma-color-ink);
}

.market__path-input {
  flex: 1;
  min-width: 200px;
}

.market__form-title {
  width: 100%;
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.market__form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  width: 100%;
}

.market__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--ma-color-ink-muted);
}

.market__field-label {
  font-size: 12px;
  color: var(--ma-color-ink-muted);
}

.market__field--wide {
  grid-column: 1 / -1;
}

.market__field textarea {
  resize: none;
}

.market__field input,
.market__field select,
.market__field textarea,
.market__path-input {
  padding: 9px 12px;
  font-family: inherit;
  font-size: 13px;
  color: var(--ma-color-ink);
  background: var(--ma-color-canvas);
  border: 1px solid transparent;
  border-radius: 10px;
  outline: none;
}

.market__field input:focus,
.market__field select:focus,
.market__field textarea:focus,
.market__path-input:focus {
  border-color: var(--ma-color-accent);
}

.market__form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  width: 100%;
}

.market__empty {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--ma-color-ink-muted);
}
</style>
