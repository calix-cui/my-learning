/**
 * 第四步「会话地址」浏览器验收：真实 Chrome + 模拟 API。
 *
 * 跑法：BASE=http://127.0.0.1:5199 pnpm acceptance:route
 *
 * 单测能验证地址与状态的对应关系，验证不了浏览器的真实历史：刷新、后退、前进、
 * 以及「设置浮层不该把会话地址吃掉」。这些只能靠真浏览器。
 */
import fs from 'node:fs/promises'
import puppeteer from 'puppeteer-core'

const BASE = process.env.BASE ?? 'http://127.0.0.1:5199'
const OUT = process.env.OUT ?? '.acceptance'
const CHROME =
  process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

const conversations = [
  { id: 1, title: '第一个会话', agent_key: 'default', skill_slug: null, update_time: '2026-11-18 20:03:00', create_time: '2026-11-18 20:00:00' },
  { id: 2, title: '第二个会话', agent_key: 'default', skill_slug: null, update_time: '2026-11-18 20:02:00', create_time: '2026-11-18 20:01:00' },
  { id: 3, title: '第三个会话', agent_key: 'default', skill_slug: null, update_time: '2026-11-18 20:01:00', create_time: '2026-11-18 20:02:00' },
]

const message = (id, conversationId, role, content) => ({
  id,
  conversation_id: conversationId,
  role,
  content,
  model: role === 'assistant' ? 'fake' : null,
  create_time: '2026-11-18 20:00:00',
})

const reply = (data) => ({
  status: 200,
  contentType: 'application/json',
  headers: { 'access-control-allow-origin': '*' },
  body: JSON.stringify({ code: 200, message: 'ok', data }),
})

const detailOf = (id) => ({
  ...conversations.find((item) => item.id === id),
  messages: [
    message(id * 10 + 1, id, 'user', `这是第 ${id} 个会话的问题`),
    message(id * 10 + 2, id, 'assistant', `这是第 ${id} 个会话的回答`),
  ],
  next_before_message_id: null,
  runs: [],
})

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu'],
})
const page = await browser.newPage()
await page.setViewport({ width: 1280, height: 800, deviceScaleFactor: 1 })

const errors = []
page.on('console', (msg) => {
  const text = msg.text()
  if (msg.type() === 'error' && !text.includes('401')) errors.push(text)
})
page.on('pageerror', (error) => errors.push(String(error)))

await page.setRequestInterception(true)
page.on('request', (request) => {
  const url = new URL(request.url())
  if (!url.pathname.startsWith('/api/')) return request.continue()
  const path = url.pathname

  if (path === '/api/auth/me') {
    return request.respond(
      reply({ id: 1, email: 'route@example.com', display_name: '地址验收', create_time: '2026-11-18 19:00:00' }),
    )
  }
  if (path === '/api/conversations' && request.method() === 'GET') {
    return request.respond(
      reply({
        items: conversations.map((item, index) => ({ ...item, message_count: index + 2 })),
        total: conversations.length,
        page: 1,
        page_size: 50,
      }),
    )
  }
  const detail = path.match(/^\/api\/conversations\/(\d+)$/)
  if (detail && request.method() === 'GET') {
    const id = Number(detail[1])
    const found = conversations.some((item) => item.id === id)
    if (!found)
      return request.respond({
        status: 404,
        contentType: 'application/json',
        headers: { 'access-control-allow-origin': '*' },
        body: JSON.stringify({ code: 40400, message: '会话不存在', data: null }),
      })
    return request.respond(reply(detailOf(id)))
  }
  if (path === '/api/agent/runs/0/steps' || path === '/api/agent/runs/0/approvals') {
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

const path = () => page.evaluate(() => location.pathname + location.search)
const body = () => page.evaluate(() => document.body.innerText)

const waitForPath = (target) =>
  page.waitForFunction((want) => location.pathname === want, { timeout: 5000 }, target)

const waitForText = (needle) =>
  page.waitForFunction(
    (want) => document.body.innerText.includes(want),
    { timeout: 5000 },
    needle,
  )

try {
  // 1. 深链直接打开指定会话
  await page.goto(`${BASE}/chat/2`, { waitUntil: 'networkidle2' })
  await waitForText('这是第 2 个会话的回答')
  check('深链直接打开指定会话', (await path()) === '/chat/2', await path())
  check('会话内容和侧栏选中一致', (await body()).includes('第二个会话'))

  // 2. 刷新后地址与会话都还在
  await page.reload({ waitUntil: 'networkidle2' })
  await waitForText('这是第 2 个会话的回答')
  check('刷新后仍停在同一会话', (await path()) === '/chat/2', await path())

  // 3. 点侧栏换会话，地址跟着换
  await page.evaluate(() => {
    const target = [...document.querySelectorAll('.chat__item-main')].find((node) =>
      node.innerText.includes('第三个会话'),
    )
    target?.click()
  })
  await waitForText('这是第 3 个会话的回答')
  check('点侧栏后地址换成该会话', (await path()) === '/chat/3', await path())

  // 4. 浏览器后退回到上一个会话
  await page.goBack()
  await waitForText('这是第 2 个会话的回答')
  check('后退回到上一个会话', (await path()) === '/chat/2', await path())

  // 5. 前进再回到第三个
  await page.goForward()
  await waitForText('这是第 3 个会话的回答')
  check('前进回到下一个会话', (await path()) === '/chat/3', await path())

  // 6. 点「新建会话」回到草稿地址
  await page.evaluate(() => document.querySelector('.chat__new')?.click())
  await waitForPath('/chat')
  const draftText = await body()
  check(
    '新建会话后地址变成 /chat 且界面空着',
    !draftText.includes('这是第 3 个会话的回答') && !draftText.includes('这是第 2 个会话的回答'),
  )

  // 7. 带 query 的会话地址：设置浮层与对话页共存，地址不被吃
  await page.goto(`${BASE}/chat/2?settings=1`, { waitUntil: 'networkidle2' })
  await waitForText('这是第 2 个会话的回答')
  const withSettings = await body()
  check('带 settings 参数的会话地址能同时打开对话和设置', withSettings.includes('模型接入'))
  check(
    '打开设置浮层不改写会话地址',
    (await path()) === '/chat/2?settings=1',
    await path(),
  )

  // 8. 收窄过的参数：不存在的路径落到 /chat
  await page.goto(`${BASE}/chat/abc`, { waitUntil: 'networkidle2' })
  await waitForPath('/chat')
  check('非数字会话地址落到 /chat', (await path()) === '/chat', await path())

  check('页面没有运行时报错', errors.length === 0, errors.join(' | '))

  await page.screenshot({ path: `${OUT}/route-chat.png`, fullPage: false })
} catch (error) {
  await fs.mkdir(OUT, { recursive: true })
  console.error('[验收失败] URL:', page.url())
  console.error('[验收失败] 页面文本:', (await body()).slice(0, 900))
  console.error('[验收失败] 控制台错误:', errors.join('\n---\n').slice(0, 2000))
  await page.screenshot({ path: `${OUT}/route-failure.png` }).catch(() => undefined)
  throw error
} finally {
  await browser.close()
}

await fs.mkdir(OUT, { recursive: true })
await fs.writeFile(`${OUT}/route-report.json`, JSON.stringify({ checks, errors }, null, 2))
console.log(JSON.stringify(checks, null, 2))
