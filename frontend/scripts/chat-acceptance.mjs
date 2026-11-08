import fs from 'node:fs/promises'
import puppeteer from 'puppeteer-core'

const BASE = process.env.BASE ?? 'http://127.0.0.1:5173'
const OUT = process.env.OUT ?? '.acceptance'
const CHROME =
  process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu', '--user-data-dir=/tmp/cp-chat'],
})
const page = await browser.newPage()
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })
const errors = []
const streamCalls = []
page.on('request', (r) => {
  if (r.url().includes('/messages/stream')) streamCalls.push(r.method() + ' ' + r.url())
})
page.on('console', (m) => {
  if (m.type() === 'error') errors.push(m.text())
})
page.on('pageerror', (e) => errors.push(String(e)))

let failures = 0
/** 清空所有会话，保证用例从空态开始（也顺手验证了列表与删除接口） */
async function cleanAll() {
  const list = await (await fetch(`${BASE}/api/conversations?page=1&page_size=100`)).json()
  for (const item of list.data.items) {
    await fetch(`${BASE}/api/conversations/${item.id}`, { method: 'DELETE' })
  }
}

const step = async (name, fn) => {
  try {
    await fn()
    console.log('PASS', name)
  } catch (e) {
    failures += 1
    console.log('FAIL', name, '-', e.message)
  }
}
await fs.mkdir(OUT, { recursive: true })

await cleanAll()
await page.goto(`${BASE}/chat`, { waitUntil: 'networkidle2' })
await page.waitForSelector('.chat', { timeout: 10000 })
console.log('title:', await page.title())

await step('UI-01 空态可见', async () => {
  const t = await page.$eval('.chat__empty-title', (el) => el.textContent.trim())
  if (!t) throw new Error('无空态标题')
})

await step('UI-02 新建会话', async () => {
  await page.click('.chat__new')
  await page.waitForSelector('.chat__item', { timeout: 5000 })
  const n = await page.$$eval('.chat__item', (els) => els.length)
  if (n < 1) throw new Error('列表无会话')
})

await step('UI-03 发送消息并收到 fake 回复', async () => {
  await page.type('.chat__composer textarea', '帮我给可口可乐设计三档定价')
  await page.click('.chat__composer .el-button--primary')
  await page.waitForFunction(
    () => document.body.innerText.includes('[fake] 收到：帮我给可口可乐设计三档定价'),
    { timeout: 15000 },
  )
  const rows = await page.$$eval('.chat__row', (els) =>
    els.map((e) => e.innerText.replace(/\s+/g, ' ').trim()),
  )
  if (!rows.some((r) => r.includes('[fake] 收到：帮我给可口可乐设计三档定价')))
    throw new Error('没看到 fake 回复: ' + JSON.stringify(rows))
})

await step('UI-03b 走的是 SSE 流式接口', async () => {
  if (streamCalls.length !== 1)
    throw new Error('stream 请求次数=' + streamCalls.length + ' ' + JSON.stringify(streamCalls))
  if (!streamCalls[0].startsWith('POST ')) throw new Error('方法=' + streamCalls[0])
})

await step('UI-04 首条消息自动命名', async () => {
  const title = await page.$eval('.chat__title', (el) => el.textContent.trim())
  if (title !== '帮我给可口可乐设计三档定价'.slice(0, 30)) throw new Error('标题=' + title)
  const itemTitle = await page.$eval('.chat__item-title', (el) => el.textContent.trim())
  if (itemTitle !== title) throw new Error('列表标题=' + itemTitle)
})

await step('UI-05 刷新后消息仍在', async () => {
  await page.reload({ waitUntil: 'networkidle2' })
  await page.waitForSelector('.chat__row', { timeout: 10000 })
  const rows = await page.$$eval('.chat__row', (els) => els.length)
  if (rows !== 2) throw new Error('刷新后行数=' + rows)
})

await step('UI-06 输入框发送后清空', async () => {
  const v = await page.$eval('.chat__composer textarea', (el) => el.value)
  if (v !== '') throw new Error('输入框残留: ' + v)
})

// 流式中间态：再发一条，抓「正在输入…」与逐字渲染
await step('UI-08 流式过程中显示增量文本', async () => {
  await page.type('.chat__composer textarea', '第二个问题看看流式')
  await page.click('.chat__composer .el-button--primary')
  await page.waitForFunction(
    () => {
      const rows = [...document.querySelectorAll('.chat__row')]
      const last = rows[rows.length - 1]
      return last?.innerText.includes('正在输入')
    },
    { timeout: 8000, polling: 20 },
  )
  const mid = await page.$$eval('.chat__row', (els) => els[els.length - 1].innerText)
  // 此刻应是半截文本 + 「正在输入…」，证明是逐块渲染而不是一次性替换
  if (!/\[fa/.test(mid)) throw new Error('增量里还没出现内容: ' + mid)
  await page.waitForFunction(() => !document.body.innerText.includes('正在输入'), {
    timeout: 15000,
  })
  const rows = await page.$$eval('.chat__row', (els) => els.length)
  if (rows !== 4) throw new Error('第二条消息后行数=' + rows)
})

await page.screenshot({ path: '.acceptance/chat-page.png' })

// 新建第二个会话，验证切换与排序
await step('UI-07 新建第二个会话后列表排序', async () => {
  await page.click('.chat__new')
  await page.waitForFunction(() => document.querySelectorAll('.chat__item').length === 2, {
    timeout: 5000,
  })
  const first = await page.$eval('.chat__item-title', (el) => el.textContent.trim())
  if (first !== '新会话') throw new Error('首位=' + first)
})

// 用页面上的删除按钮清掉当前会话（顺带验证删除交互），其余交给接口清理
await step('UI-09 会话删除需二次确认', async () => {
  await page.click('.chat__item')
  await page.hover('.chat__item')
  await page.waitForSelector('.chat__item-actions', { visible: true })
  await page.click('.chat__item-actions .el-button:last-child')
  await page.waitForSelector('.el-message-box', { visible: true })
  await page.click('.el-message-box .el-button--primary')
  await page.waitForFunction(() => document.querySelectorAll('.chat__item').length === 1, {
    timeout: 5000,
  })
})

await cleanAll()
const left = (await (await fetch(`${BASE}/api/conversations`)).json()).data.total
console.log('leftover conversations:', left)

console.log('console errors:', errors.length ? errors : 'none')
await browser.close()

await browser.close()
console.log(`\n${failures === 0 ? '全部通过' : failures + ' 项失败'}；截图：${OUT}/chat-page.png`)
process.exit(failures === 0 ? 0 : 1)
