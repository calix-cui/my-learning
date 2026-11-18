/**
 * 第三步「统一执行状态」浏览器验收：真实 Chrome + 模拟 API/SSE。
 *
 * 跑法：BASE=http://127.0.0.1:5199 pnpm acceptance:recovery
 *
 * 验证的是「断流之后用户看到什么、还能不能点」：
 * 1. 流没收到终态就断开时，出现恢复提示并锁住发送；
 * 2. 提示里的「重新核对状态」只查历史、不重发消息；
 * 3. 核对到持久化的终态后恢复正式正文并解锁发送。
 * 这不是真实模型验收，只证明前端在断流路径上的行为。
 */
import fs from 'node:fs/promises'
import puppeteer from 'puppeteer-core'

const BASE = process.env.BASE ?? 'http://127.0.0.1:5199'
const OUT = process.env.OUT ?? '.acceptance'
const CHROME =
  process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

const RUN_ID = 7
const USER_MESSAGE = {
  id: 11,
  conversation_id: 1,
  role: 'user',
  content: '帮我看一下明天的天气',
  model: null,
  create_time: '2026-11-18 19:40:00',
}
const ASSISTANT_MESSAGE = {
  id: 12,
  conversation_id: 1,
  role: 'assistant',
  content: '明天多云，最高 21 度。',
  model: 'fake',
  create_time: '2026-11-18 19:40:03',
}

/**
 * 断流验收的状态机：
 * idle（还没有运行）→ 发消息后 running（核对前运行仍在跑）→ completed（核对后已持久化）
 */
const state = { phase: 'idle', streamPosts: 0, historyReads: 0 }
/** 记下所有打到 /api 的请求，报告里能看清前端到底发了什么 */
const requests = []

const conversation = {
  id: 1,
  title: '断流恢复验收',
  agent_key: 'default',
  skill_slug: null,
  update_time: '2026-11-18 19:40:03',
  create_time: '2026-11-18 19:39:00',
}

const reply = (data) => ({
  status: 200,
  contentType: 'application/json',
  headers: { 'access-control-allow-origin': '*' },
  body: JSON.stringify({ code: 200, message: 'ok', data }),
})

const detail = () => {
  const runs =
    state.phase === 'idle'
      ? []
      : [
          {
            id: RUN_ID,
            user_message_id: USER_MESSAGE.id,
            assistant_message_id: state.phase === 'completed' ? ASSISTANT_MESSAGE.id : null,
            status: state.phase === 'completed' ? 'completed' : 'running',
            visible_step_count: 0,
          },
        ]
  const messages =
    state.phase === 'idle'
      ? []
      : state.phase === 'completed'
        ? [USER_MESSAGE, ASSISTANT_MESSAGE]
        : [USER_MESSAGE]
  return { ...conversation, messages, next_before_message_id: null, runs }
}

/** 只发到一半就结束的 SSE：没有 run_finished，正是「结果未知」那种断流 */
const brokenStream = () =>
  [
    `data: ${JSON.stringify({ type: 'run_started', run_id: RUN_ID, conversation_id: 1, user_message_id: USER_MESSAGE.id })}`,
    `data: ${JSON.stringify({ type: 'assistant_delta', content: '正在查询' })}`,
    '',
  ].join('\n\n')

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu'],
})
const page = await browser.newPage()
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })

const errors = []
page.on('console', (message) => {
  const text = message.text()
  if (message.type() === 'error' && !text.includes('401')) errors.push(text)
})
page.on('pageerror', (error) => errors.push(String(error)))

await page.setRequestInterception(true)
page.on('request', async (request) => {
  const url = new URL(request.url())
  if (!url.pathname.startsWith('/api/')) return request.continue()
  const path = url.pathname
  const method = request.method()
  requests.push(`${method} ${path}`)

  if (path === '/api/auth/me') {
    return request.respond(
      reply({ id: 1, email: 'recovery@example.com', display_name: '恢复验收', create_time: '2026-11-18 19:00:00' }),
    )
  }
  if (path === '/api/conversations' && method === 'GET') {
    return request.respond(
      reply({ items: [{ ...conversation, message_count: 2 }], total: 1, page: 1, page_size: 50 }),
    )
  }
  if (path === '/api/conversations/1' && method === 'GET') {
    state.historyReads += 1
    return request.respond(reply(detail()))
  }
  if (path === '/api/conversations/1/messages/stream' && method === 'POST') {
    state.streamPosts += 1
    // 消息发出后后端确实建了运行，只是这条 SSE 没发终态就断了
    state.phase = 'running'
    return request.respond({
      status: 200,
      contentType: 'text/event-stream',
      headers: { 'cache-control': 'no-cache', 'access-control-allow-origin': '*' },
      body: brokenStream(),
    })
  }
  if (/^\/api\/agent\/runs\/\d+\/(steps|approvals)$/.test(path)) {
    return request.respond(reply({ items: [] }))
  }
  if (path === '/api/skills/catalog/rescan') {
    return request.respond(reply({ items: [], version: 'acceptance-v1', legacy_count: 0 }))
  }
  return request.respond(reply({}))
})

const checks = []
const check = (name, ok, detailText = '') => {
  checks.push({ name, ok, detail: detailText })
  if (!ok) throw new Error(`验收失败：${name}${detailText ? `（${detailText}）` : ''}`)
}

const text = () => page.evaluate(() => document.body.innerText)
const sendDisabled = () =>
  page.$eval('button[aria-label="发送"]', (button) => button.disabled)

try {
  await page.goto(`${BASE}/chat/1`, { waitUntil: 'networkidle2' })
  await page
    .evaluate(() => document.getElementById('__vue-devtools-container__')?.remove())
    .catch(() => undefined)
  await page.waitForSelector('textarea[aria-label="消息内容"]')
  check('打开会话后有输入框', true)

  await page.type('textarea[aria-label="消息内容"]', '帮我看一下明天的天气')
  await page.click('button[aria-label="发送"]')

  await page.waitForSelector('.chat__recovery', { visible: true })
  const banner = await page.$eval('.chat__recovery', (node) => node.innerText)
  check('断流后显示恢复提示', banner.includes('核对'), banner)
  check('断流后锁住发送', await sendDisabled())
  check('断流后确实只发过一次消息', state.streamPosts === 1, `POST ${state.streamPosts} 次`)
  check('断流后没有凭空出现助手正文', !(await text()).includes(ASSISTANT_MESSAGE.content))

  await page.screenshot({ path: `${OUT}/recovery-disconnected.png`, fullPage: false })

  state.phase = 'completed'
  await page.click('.chat__recovery button')
  await page.waitForFunction(
    (expected) => document.body.innerText.includes(expected),
    { timeout: 5000 },
    ASSISTANT_MESSAGE.content,
  )
  check('核对后恢复正式正文', (await text()).includes(ASSISTANT_MESSAGE.content))
  check('核对后不再显示恢复提示', (await page.$('.chat__recovery')) === null)
  const composer = await page.$eval('textarea[aria-label="消息内容"]', (node) => ({
    disabled: node.disabled,
    value: node.value,
  }))
  check('核对后输入框恢复可用', !composer.disabled)
  check('核对只查历史、不重发消息', state.streamPosts === 1, `POST ${state.streamPosts} 次`)
  check('核对确实重新读了会话历史', state.historyReads >= 2, `GET ${state.historyReads} 次`)
  check('核对后不再留着已经发出去的草稿', composer.value === '', `输入框：${composer.value}`)
  check('页面没有运行时报错', errors.length === 0, errors.join(' | '))

  await page.screenshot({ path: `${OUT}/recovery-restored.png`, fullPage: false })
} catch (error) {
  await fs.mkdir(OUT, { recursive: true })
  console.error('[验收失败] URL:', page.url())
  console.error('[验收失败] 页面文本:', (await text()).slice(0, 900))
  console.error('[验收失败] 控制台错误:', errors.join('\n---\n').slice(0, 2000))
  console.error('[验收失败] /api 请求:', requests.join('\n'))
  await page.screenshot({ path: `${OUT}/recovery-failure.png` }).catch(() => undefined)
  throw error
} finally {
  await browser.close()
}

await fs.mkdir(OUT, { recursive: true })
await fs.writeFile(`${OUT}/recovery-report.json`, JSON.stringify({ checks, state, requests, errors }, null, 2))
console.log(JSON.stringify(checks, null, 2))
