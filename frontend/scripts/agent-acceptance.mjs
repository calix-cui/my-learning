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
  args: ['--no-sandbox', '--disable-gpu'],
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
  if (request.url().includes('/messages/stream'))
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
  const checked = await page.evaluate(
    () => document.querySelector('.chat__mode--reasoning')?.getAttribute('aria-pressed') === 'true',
  )
  if (checked) throw new Error('深度回答默认是开着的')
})

await step('A-02 有推理能力时可独立开启和关闭「深度回答」', async () => {
  const control = await page.$('.chat__mode--reasoning')
  if (!control) return
  await control.click()
  if ((await control.evaluate((el) => el.getAttribute('aria-pressed'))) !== 'true') {
    throw new Error('推理开关未开启')
  }
  await control.click()
  if ((await control.evaluate((el) => el.getAttribute('aria-pressed'))) !== 'false') {
    throw new Error('推理开关未关闭')
  }
})

await step('A-03 新建会话并发送需要工具的问题', async () => {
  await page.click('.chat__new')
  await page.waitForSelector('.chat__empty-title', { timeout: 5000 })
  await page.type('.chat__composer textarea', '用工具算 3 的 5 次方，然后用一句话告诉我结果')
  await page.click('.chat__composer .el-button--primary')
  // 会话在第一条消息发出时才创建
  await page.waitForSelector('.chat__item', { timeout: 10000 })
})

await step('A-04 普通聊天走统一消息流接口', async () => {
  await page.waitForFunction(() => document.querySelector('.timeline'), { timeout: 60000 })
  if (agentCalls.length !== 1) throw new Error(`agent 请求次数=${agentCalls.length}`)
  if (!agentCalls[0].startsWith('POST ')) throw new Error(`方法不对：${agentCalls[0]}`)
})

await step('A-05 时间线出现工具调用与结果', async () => {
  await waitIdle()
  await page.waitForFunction(
    () => document.querySelectorAll('.timeline__item--tool_result').length >= 1,
    { timeout: 60000 },
  )
  await page.click('.timeline > summary')
  await page.click('.timeline__item--tool_result > summary')
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

await step('A-07 刷新和切换会话后可分别回放两条回复的工具结果', async () => {
  const conversationUrl = page.url()
  await page.type('.chat__composer textarea', '用工具计算 6 乘以 7，再告诉我结果')
  await page.click('.chat__composer .el-button--primary')
  await page.waitForFunction(
    () => document.querySelectorAll('.chat__row--assistant').length === 2,
    { timeout: 60000 },
  )
  await waitIdle()
  const another = await api('/api/conversations', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ title: '另一个会话' }),
  })
  if (!another.ok) throw new Error('创建切换验证会话失败')
  await page.reload({ waitUntil: 'networkidle2' })
  const conversationTitle = await page.$eval('.chat__item-main[aria-current="true"]', (el) =>
    el.textContent.trim(),
  )

  const verifyReplay = async (index, expected) => {
    await page.waitForFunction(
      () => document.querySelectorAll('.chat__row--assistant + .timeline').length === 2,
      { timeout: 15000 },
    )
    const timelines = await page.$$('.chat__row--assistant + .timeline')
    const timeline = timelines[index]
    const summary = await timeline.$('summary')
    await summary.click()
    await page.waitForFunction(
      (element) => element.querySelector('.timeline__item--tool_result'),
      { timeout: 15000 },
      timeline,
    )
    const row = await timeline.$('.timeline__item--tool_result > summary')
    await row.click()
    const result = await timeline.$eval('.timeline__item--tool_result .timeline__text', (el) =>
      (el.textContent ?? '').trim(),
    )
    if (!result.includes(expected)) throw new Error(`期望工具结果 ${expected}，实际为 ${result}`)
  }
  await verifyReplay(0, '243')
  await verifyReplay(1, '42')

  const switchTo = async (title) => {
    const buttons = await page.$$('.chat__item-main')
    for (const button of buttons) {
      if ((await button.evaluate((el) => el.textContent.trim())) === title) {
        await button.click()
        return
      }
    }
    throw new Error(`会话列表找不到 ${title}`)
  }
  await switchTo('另一个会话')
  await page.waitForSelector('.chat__empty-title')
  if (await page.$('.timeline')) throw new Error('另一会话中出现了旧对话的执行过程')
  await switchTo(conversationTitle)
  await page.waitForFunction((url) => location.href === url, {}, conversationUrl)
  await verifyReplay(0, '243')
  await page.screenshot({ path: `${OUT}/agent-02-replay.png` })
})

await step('A-08 普通问候复用同一接口且不需要工具', async () => {
  const before = agentCalls.length
  const beforeCount = await page.$$eval('.chat__row--assistant', (els) => els.length)
  await page.type('.chat__composer textarea', '一句话介绍你自己')
  await page.click('.chat__composer .el-button--primary')
  await waitIdle()
  const afterCount = await page.$$eval('.chat__row--assistant', (els) => els.length)
  if (afterCount !== beforeCount + 1) {
    throw new Error(`助手气泡数 ${beforeCount} → ${afterCount}`)
  }
  if (agentCalls.length !== before + 1) throw new Error('问候没有使用同一消息流接口')
  if ((await page.$$('.chat__row--assistant + .timeline')).length !== 2) {
    throw new Error('普通回复后原有执行记录的数量发生变化')
  }
  await page.screenshot({ path: `${OUT}/agent-03-normal.png` })
})

await step('A-09 后端记录了这次运行', async () => {
  // 普通问候也有运行记录，从两条调用工具的回复核对步骤。
  const conversationId = new URL(page.url()).pathname.split('/').at(-1)
  const runs = await (await api(`/api/conversations/${conversationId}/agent/runs`)).json()
  const toolRuns = runs.data.items.filter((run) =>
    run.steps.some((step) => step.kind === 'tool_call'),
  )
  if (toolRuns.length !== 2) throw new Error(`带工具的运行数量=${toolRuns.length}`)
  for (const run of toolRuns) {
    if (run.status !== 'completed') throw new Error(`状态=${run.status}`)
    if (!run.steps.some((step) => step.kind === 'tool_result')) {
      throw new Error('运行缺少工具结果')
    }
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
