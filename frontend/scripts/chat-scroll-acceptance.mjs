/**
 * 第四步「消息区滚动」浏览器验收：真实 Chrome + 模拟 API。
 *
 * 跑法：BASE=http://127.0.0.1:5199 pnpm acceptance:scroll
 *
 * 单元测试（useChatScroll.test.ts）用可控几何验证策略，这里补的是真实排版下的
 * 几何行为——打开会话是否停在底部、往上翻页时正在读的那一行会不会被顶走。
 * 流式增量跟随没法用静态 mock 复现，那部分由单元测试覆盖。
 */
import fs from 'node:fs/promises'
import puppeteer from 'puppeteer-core'

const BASE = process.env.BASE ?? 'http://127.0.0.1:5199'
const OUT = process.env.OUT ?? '.acceptance'
const CHROME =
  process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

const conversation = {
  id: 1,
  title: '滚动验收',
  agent_key: 'default',
  skill_slug: null,
  update_time: '2026-11-18 20:00:00',
  create_time: '2026-11-18 19:00:00',
}

/** 30 条历史，分 3 页各 10 条，游标是「比它更早的消息」 */
const allMessages = Array.from({ length: 30 }, (_, index) => {
  const id = index + 1
  return {
    id,
    conversation_id: 1,
    role: id % 2 === 1 ? 'user' : 'assistant',
    content: `历史消息 ${id}`,
    model: id % 2 === 0 ? 'fake' : null,
    create_time: '2026-11-18 19:00:00',
  }
})

const PAGE_SIZE = 10
const historyReads = []

const reply = (data) => ({
  status: 200,
  contentType: 'application/json',
  headers: { 'access-control-allow-origin': '*' },
  body: JSON.stringify({ code: 200, message: 'ok', data }),
})

/** before 为空取最新一页；否则取 id 小于 before 的一页 */
function detail(before) {
  const older = before === undefined ? allMessages.length : before - 1
  const start = Math.max(0, older - PAGE_SIZE)
  const page = allMessages.slice(start, older)
  return {
    ...conversation,
    messages: page,
    next_before_message_id: start > 0 ? page[0].id : null,
    runs: [],
  }
}

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu'],
})
const page = await browser.newPage()
// 小窗口更容易让内容溢出，翻页时的高度差也更明显
await page.setViewport({ width: 1280, height: 720, deviceScaleFactor: 1 })

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

  if (path === '/api/auth/me') {
    return request.respond(
      reply({
        id: 1,
        email: 'scroll@example.com',
        display_name: '滚动验收',
        create_time: '2026-11-18 19:00:00',
      }),
    )
  }
  if (path === '/api/conversations' && request.method() === 'GET') {
    return request.respond(
      reply({ items: [{ ...conversation, message_count: 30 }], total: 1, page: 1, page_size: 50 }),
    )
  }
  if (path === '/api/conversations/1' && request.method() === 'GET') {
    const before = url.searchParams.get('before_message_id')
    historyReads.push(before ?? 'latest')
    return request.respond(reply(detail(before === null ? undefined : Number(before))))
  }
  if (path === '/api/agent/runs/1/steps' || path === '/api/agent/runs/1/approvals') {
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

const scrollerMetrics = () =>
  page.$eval('.chat__scroll', (node) => ({
    scrollTop: node.scrollTop,
    scrollHeight: node.scrollHeight,
    clientHeight: node.clientHeight,
  }))

/** 某条消息相对视口的位置；翻页前后应当基本不变 */
const markerTop = (content) =>
  page.evaluate((needle) => {
    const row = [...document.querySelectorAll('.chat__row')].find((node) =>
      node.innerText.includes(needle),
    )
    return row ? row.getBoundingClientRect().top : null
  }, content)

const setScroll = (top) =>
  page.$eval(
    '.chat__scroll',
    (node, value) => {
      node.scrollTop = value
    },
    top,
  )

const text = () => page.evaluate(() => document.body.innerText)

try {
  await page.goto(`${BASE}/chat/1`, { waitUntil: 'networkidle2' })
  await page
    .evaluate(() => document.getElementById('__vue-devtools-container__')?.remove())
    .catch(() => undefined)
  await page.waitForSelector('.chat__row')

  const opened = await scrollerMetrics()
  check(
    '打开会话后停在最底部',
    opened.scrollHeight > opened.clientHeight &&
      opened.scrollTop + opened.clientHeight >= opened.scrollHeight - 2,
    `scrollTop=${opened.scrollTop} height=${opened.scrollHeight} client=${opened.clientHeight}`,
  )

  const button = await page.waitForSelector('.chat__older', { visible: true })
  check('还有更早消息时给出翻页入口', button !== null)

  // 翻页入口在列表顶部：真实的翻页必然是「先滚到顶部再点」，所以锚点要在顶部验证。
  // 用 evaluate 点击而不是 page.click，避免 Puppeteer 为点击把入口滚进视口、改掉起始位置。
  const clickOlder = () => page.evaluate(() => document.querySelector('.chat__older')?.click())

  await setScroll(0)
  const buttonBox = await page.$eval('.chat__older', (node) => {
    const rect = node.getBoundingClientRect()
    const scroll = node.closest('.chat__scroll').getBoundingClientRect()
    return { top: rect.top, bottom: rect.bottom, viewTop: scroll.top, viewBottom: scroll.bottom }
  })
  check(
    '滚到顶部后翻页入口完整可见',
    buttonBox.top >= buttonBox.viewTop && buttonBox.bottom <= buttonBox.viewBottom,
    JSON.stringify(buttonBox),
  )

  const beforeFirst = await markerTop('历史消息 22')
  await clickOlder()
  await page.waitForFunction(() => document.body.innerText.includes('历史消息 15'), {
    timeout: 5000,
  })
  const afterFirst = await markerTop('历史消息 22')
  const firstMetrics = await scrollerMetrics()
  check(
    '翻页后正在读的那条不跳位',
    beforeFirst !== null && afterFirst !== null && Math.abs(afterFirst - beforeFirst) <= 2,
    `${beforeFirst} → ${afterFirst}`,
  )
  check(
    '翻页补上了新增内容的高度',
    firstMetrics.scrollTop >= 500,
    `scrollTop=${firstMetrics.scrollTop}（页面高度 ${firstMetrics.scrollHeight}）`,
  )

  await page.screenshot({ path: `${OUT}/scroll-page2.png`, fullPage: false })

  // 第二页：再滚回顶部翻一次，锚点同样要保住
  await setScroll(0)
  const beforeSecond = await markerTop('历史消息 12')
  await clickOlder()
  await page.waitForFunction(() => document.body.innerText.includes('历史消息 5'), {
    timeout: 5000,
  })
  const afterSecond = await markerTop('历史消息 12')
  check(
    '连续翻页仍然不跳位',
    beforeSecond !== null && afterSecond !== null && Math.abs(afterSecond - beforeSecond) <= 2,
    `${beforeSecond} → ${afterSecond}`,
  )

  const oldestLoaded = (await text()).includes('历史消息 1')
  check('最后一页加载完成后最早的消息可见', oldestLoaded)
  const stillHasButton = (await page.$('.chat__older')) !== null
  check('没有更早消息后收起翻页入口', !stillHasButton)
  check(
    '每次翻页只多读一页历史',
    historyReads.length === 3,
    `GET /conversations/1 ${historyReads.join(' → ')}`,
  )
  check('页面没有运行时报错', errors.length === 0, errors.join(' | '))

  await page.screenshot({ path: `${OUT}/scroll-top.png`, fullPage: false })
} catch (error) {
  await fs.mkdir(OUT, { recursive: true })
  console.error('[验收失败] URL:', page.url())
  console.error('[验收失败] 页面文本:', (await text()).slice(0, 900))
  console.error('[验收失败] 控制台错误:', errors.join('\n---\n').slice(0, 2000))
  console.error('[验收失败] 历史读取:', historyReads.join(' → '))
  await page.screenshot({ path: `${OUT}/scroll-failure.png` }).catch(() => undefined)
  throw error
} finally {
  await browser.close()
}

await fs.mkdir(OUT, { recursive: true })
await fs.writeFile(
  `${OUT}/scroll-report.json`,
  JSON.stringify({ checks, historyReads, errors }, null, 2),
)
console.log(JSON.stringify(checks, null, 2))
