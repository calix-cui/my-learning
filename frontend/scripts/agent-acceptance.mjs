/**
 * 阶段 5「深度回答」端到端验收：真实浏览器 + 真实模型（或 fake），不 mock 前端。
 *
 * 跑法：BASE=http://127.0.0.1:5173 pnpm acceptance:agent
 * 断言点是「用户能否看见工具过程」，所以既查 DOM 也查后端返回的运行记录。
 */
import fs from 'node:fs/promises'
import puppeteer from 'puppeteer-core'

const BASE = process.env.BASE ?? 'http://127.0.0.1:5173'
const OUT = process.env.OUT ?? '.acceptance'
const CHROME =
  process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu', '--user-data-dir=/tmp/cp-agent-e2e'],
})
const page = await browser.newPage()
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })

// vue-devtools 的悬浮面板会挡住点击，导航后移除
const gotoPage = async (url) => {
  await page.goto(url, { waitUntil: 'networkidle2' })
  await page
    .evaluate(() => document.getElementById('__vue-devtools-container__')?.remove())
    .catch(() => undefined)
}

const errors = []
const agentCalls = []
page.on('request', (request) => {
  if (request.url().includes('/agent/stream'))
    agentCalls.push(`${request.method()} ${request.url()}`)
})
page.on('console', (message) => {
  const text = message.text()
  // 启动时的 /auth/me 401 与登录失败属预期，不计入错误
  if (message.type() === 'error' && !text.includes('401')) errors.push(text)
})
page.on('pageerror', (error) => errors.push(String(error)))

const email = `agent-e2e-${Date.now()}@example.com`
const registerResponse = await fetch(`${BASE}/api/auth/register`, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ email, password: 'password123' }),
})
if (!registerResponse.ok) {
  throw new Error(`注册失败：${registerResponse.status} ${await registerResponse.text()}`)
}
const sessionCookie = registerResponse.headers
  .getSetCookie()
  .map((cookie) => cookie.split(';')[0])
  .find((cookie) => cookie.startsWith('my_agent_session='))
if (!sessionCookie) throw new Error('注册响应没有下发 my_agent_session Cookie')

const api = (path, init = {}) =>
  fetch(`${BASE}${path}`, { ...init, headers: { ...(init.headers ?? {}), cookie: sessionCookie } })

let failures = 0

/**
 * 等一次发送彻底结束。
 *
 * 注意不能只等 `.chat__row--assistant`：流式占位气泡也带这个类，
 * 会在真正落库前就通过，随后 reload 会把还没提交的流掐断（消息就没了）。
 */
const waitIdle = async (timeout = 90000) => {
  await page.waitForFunction(() => !document.querySelector('.chat__bubble--streaming'), { timeout })
  await page.waitForFunction(
    () => !document.querySelector('.chat__composer .el-button.is-loading'),
    { timeout },
  )
}

const step = async (name, fn) => {
  try {
    await fn()
    console.log('PASS', name)
  } catch (error) {
    failures += 1
    console.log('FAIL', name, '-', error.message)
  }
}

await fs.mkdir(OUT, { recursive: true })
const origin = new URL(BASE)
await page.setCookie({
  name: 'my_agent_session',
  value: sessionCookie.split('=')[1],
  domain: origin.hostname,
  path: '/',
  httpOnly: true,
})

await gotoPage(`${BASE}/chat`)
await page.waitForSelector('.chat', { timeout: 10000 })
// 从空态开始，避免旧会话干扰断言
const before = await (await api('/api/conversations?page=1&page_size=100')).json()
for (const item of before.data.items) {
  await api(`/api/conversations/${item.id}`, { method: 'DELETE' })
}
await page.reload({ waitUntil: 'networkidle2' })
await page.waitForSelector('.chat__empty-title', { timeout: 10000 })

await step('A-01 默认是普通对话，没有时间线', async () => {
  if (await page.$('.timeline')) throw new Error('默认就显示了时间线')
  const checked = await page.$eval('.chat__mode .el-switch', (el) =>
    el.classList.contains('is-checked'),
  )
  if (checked) throw new Error('深度回答默认是开着的')
})

await step('A-02 打开「深度回答」', async () => {
  await page.click('.chat__mode .el-switch')
  await page.waitForFunction(
    () => document.querySelector('.chat__mode .el-switch')?.classList.contains('is-checked'),
    { timeout: 5000 },
  )
})

await step('A-03 新建会话并发送需要工具的问题', async () => {
  await page.click('.chat__new')
  await page.waitForSelector('.chat__item', { timeout: 5000 })
  await page.type('.chat__composer textarea', '用工具算 3 的 5 次方，然后用一句话告诉我结果')
  await page.click('.chat__composer .el-button--primary')
})

await step('A-04 请求走的是 agent 流式接口', async () => {
  await page.waitForFunction(() => document.querySelector('.timeline'), { timeout: 60000 })
  if (agentCalls.length !== 1) throw new Error(`agent 请求次数=${agentCalls.length}`)
  if (!agentCalls[0].startsWith('POST ')) throw new Error(`方法不对：${agentCalls[0]}`)
})

await step('A-05 时间线出现工具调用与结果', async () => {
  await page.waitForFunction(
    () => document.querySelectorAll('.timeline__item--tool_result').length >= 1,
    { timeout: 60000 },
  )
  const tools = await page.$$eval('.timeline__tool', (els) =>
    els.map((el) => el.textContent.trim()),
  )
  if (!tools.includes('calculator')) throw new Error(`工具名=${JSON.stringify(tools)}`)
  const result = await page.$eval('.timeline__item--tool_result .timeline__text', (el) =>
    (el.textContent ?? '').trim(),
  )
  if (!result.includes('243')) throw new Error(`工具结果=${result}`)
  console.log('   工具结果:', result)
})

await step('A-06 最终答复进了气泡并含正确数字', async () => {
  await waitIdle()
  const bubbles = await page.$$eval('.chat__row--assistant .chat__content', (els) =>
    els.map((el) => (el.textContent ?? '').trim()),
  )
  if (!bubbles.length) throw new Error('没有助手气泡')
  if (!bubbles[bubbles.length - 1].includes('243')) {
    throw new Error(`最终答复=${bubbles[bubbles.length - 1].slice(0, 60)}`)
  }
  await page.screenshot({ path: `${OUT}/agent-01-timeline.png` })
})

await step('A-07 刷新后仍能看到上次的工具过程', async () => {
  await page.reload({ waitUntil: 'networkidle2' })
  await page.waitForSelector('.timeline', { timeout: 15000 })
  const tools = await page.$$eval('.timeline__tool', (els) =>
    els.map((el) => el.textContent.trim()),
  )
  if (!tools.includes('calculator')) throw new Error(`回放里没有工具：${JSON.stringify(tools)}`)
  await page.screenshot({ path: `${OUT}/agent-02-replay.png` })
})

await step('A-08 关掉开关后回到普通对话', async () => {
  await page.click('.chat__mode .el-switch')
  await page.waitForFunction(
    () => !document.querySelector('.chat__mode .el-switch')?.classList.contains('is-checked'),
    { timeout: 5000 },
  )
  const before = agentCalls.length
  const beforeCount = await page.$$eval('.chat__row--assistant', (els) => els.length)
  await page.type('.chat__composer textarea', '一句话介绍你自己')
  await page.click('.chat__composer .el-button--primary')
  await waitIdle()
  const afterCount = await page.$$eval('.chat__row--assistant', (els) => els.length)
  if (afterCount !== beforeCount + 1) {
    throw new Error(`助手气泡数 ${beforeCount} → ${afterCount}`)
  }
  if (agentCalls.length !== before) throw new Error('关掉后仍然走了 agent 接口')
  await page.screenshot({ path: `${OUT}/agent-03-normal.png` })
})

await step('A-09 后端记录了这次运行', async () => {
  // 取最新会话的运行记录，确认步骤落库（工具名、参数、状态）
  const list = await (await api('/api/conversations?page=1&page_size=5')).json()
  const conversationId = list.data.items[0].id
  const runs = await (await api(`/api/conversations/${conversationId}/agent/runs`)).json()
  const run = runs.data.items[0]
  if (!run) throw new Error('没有运行记录')
  if (run.status !== 'completed') throw new Error(`状态=${run.status}`)
  const kinds = run.steps.map((s) => s.kind)
  if (!kinds.includes('tool_call') || !kinds.includes('tool_result')) {
    throw new Error(`步骤=${JSON.stringify(kinds)}`)
  }
})

await step('A-10 控制台无非预期报错', async () => {
  if (errors.length) throw new Error(errors.slice(0, 2).join(' | '))
})

// 清理这次验收创建的会话
const after = await (await api('/api/conversations?page=1&page_size=100')).json()
for (const item of after.data.items) {
  await api(`/api/conversations/${item.id}`, { method: 'DELETE' })
}

await browser.close()
console.log(failures === 0 ? '\n全部通过' : `\n失败 ${failures} 项`)
process.exit(failures === 0 ? 0 : 1)
