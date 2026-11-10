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

// vue-devtools 的悬浮面板固定在页面中央，headless 下会挡住按钮的鼠标点击；
// 每次导航后移除它（插件本身只在 dev 注入，不影响产物）。
const gotoPage = async (url) => {
  await page.goto(url, { waitUntil: 'networkidle2' })
  await page
    .evaluate(() => document.getElementById('__vue-devtools-container__')?.remove())
    .catch(() => undefined)
}

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

/**
 * 账号体系上线后，所有业务接口都要求登录。
 * 这里先注册一个一次性账号拿到 Cookie：浏览器侧塞进 page，fetch 侧放进 Cookie 头。
 */
const email = `chat-e2e-${Date.now()}@example.com`
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
  .map((c) => c.split(';')[0])
  .find((c) => c.startsWith('my_agent_session='))
if (!sessionCookie) {
  throw new Error('注册响应没有下发 my_agent_session Cookie')
}
const sessionToken = sessionCookie.split('=')[1]
/** 带登录态的 fetch（脚本里所有 REST 断言都走它） */
const api = (path, init = {}) =>
  fetch(`${BASE}${path}`, { ...init, headers: { ...(init.headers ?? {}), cookie: sessionCookie } })
/** 注册可能返回 403（注册关闭），给出可读原因 */
if (!registerResponse.ok) throw new Error('无法创建测试账号')

let failures = 0
/** 清空所有会话，保证用例从空态开始（也顺手验证了列表与删除接口） */
async function cleanAll() {
  const list = await (await api('/api/conversations?page=1&page_size=100')).json()
  for (const item of list.data.items) {
    await api(`/api/conversations/${item.id}`, { method: 'DELETE' })
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
// 把会话 Cookie 塞进浏览器，等价于「已登录用户打开对话页」
const origin = new URL(BASE)
await page.setCookie({
  name: 'my_agent_session',
  value: sessionToken,
  domain: origin.hostname,
  path: '/',
  httpOnly: true,
})
await gotoPage(`${BASE}/chat`)
await page.waitForSelector('.chat', { timeout: 10000 })
console.log('title:', await page.title())

await step('UI-01 空态可见', async () => {
  const t = await page.$eval('.chat__empty-title', (el) => el.textContent.trim())
  if (!t) throw new Error('无空态标题')
})

await step('UI-02 新建会话只进草稿态（不落库）', async () => {
  await page.click('.chat__new')
  // 只切到「空白新会话」，后端还不该有记录：列表里仍是 0 条
  await page.waitForSelector('.chat__empty-title', { timeout: 5000 })
  const n = await page.$$eval('.chat__item', (els) => els.length)
  if (n !== 0) throw new Error('草稿态不该建会话，实际=' + n)
})

await step('UI-03 发送消息并收到回复', async () => {
  await page.type('.chat__composer textarea', '帮我给可口可乐设计三档定价')
  await page.click('.chat__composer .el-button--primary')
  // 真实模型与 fake 模型回复内容不同，这里只等助手气泡出现且非空
  await page.waitForSelector('.chat__row--assistant .chat__content', { timeout: 60000 })
  await page.waitForFunction(
    () => !document.querySelector('.chat__composer .el-button.is-loading'),
    { timeout: 60000 },
  )
  const reply = await page.$eval('.chat__row--assistant .chat__content', (el) =>
    (el.textContent ?? '').trim(),
  )
  if (!reply) throw new Error('助手回复为空')
  // 第一条消息发出去之后才真正建会话
  await page.waitForSelector('.chat__item', { timeout: 10000 })
  console.log('   回复首段:', reply.slice(0, 40).replace(/\n/g, ' '))
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
await step('UI-08 流式回复确实是分块到达', async () => {
  // 真实模型的首字可能几百毫秒就结束，靠轮询 DOM 抓「半截文本」必然偶发失败；
  // 这里在 fetch 层数 SSE 的 delta 帧——它同时说明「链路上没有被整段缓冲」。
  await page.evaluate(() => {
    window.__deltaCount = 0
    const originalFetch = window.fetch.bind(window)
    window.fetch = async (...args) => {
      const response = await originalFetch(...args)
      const url = String(args[0])
      if (url.includes('/messages/stream')) {
        const clone = response.clone()
        void (async () => {
          const reader = clone.body?.getReader()
          if (!reader) return
          const decoder = new TextDecoder()
          let buffer = ''
          for (;;) {
            const { done, value } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true })
            const frames = buffer.split('\n\n')
            buffer = frames.pop() ?? ''
            for (const frame of frames) {
              if (frame.includes('"type": "delta"') || frame.includes('"type":"delta"')) {
                window.__deltaCount += 1
              }
            }
          }
        })()
      }
      return response
    }
  })

  await page.type('.chat__composer textarea', '第二个问题看看流式，请多说两句')
  await page.click('.chat__composer .el-button--primary')

  // 点下发送后立刻要有状态提示（等待首字时也不该静默）
  await page.waitForFunction(() => document.body.innerText.includes('正在输入'), {
    timeout: 5000,
    polling: 20,
  })

  await page.waitForFunction(() => !document.body.innerText.includes('正在输入'), {
    timeout: 60000,
  })
  await new Promise((resolve) => setTimeout(resolve, 500))

  const deltas = await page.evaluate(() => window.__deltaCount)
  if (deltas < 2) throw new Error('delta 帧数=' + deltas + '，说明被整段返回了')

  const rows = await page.$$eval('.chat__row', (els) => els.length)
  if (rows !== 4) throw new Error('第二条消息后行数=' + rows)
})

await page.screenshot({ path: '.acceptance/chat-page.png' })

// 新建第二个会话，验证切换与排序
await step('UI-07 新建第二个会话后列表排序', async () => {
  await page.click('.chat__new')
  await page.waitForSelector('.chat__empty-title', { timeout: 5000 })
  const before = await page.$$eval('.chat__item', (els) => els.length)
  if (before !== 1) throw new Error('草稿态不该新增会话，实际=' + before)

  await page.type('.chat__composer textarea', '第二段对话')
  await page.click('.chat__composer .el-button--primary')
  // 列表项是在服务端建会话后才有，标题要等 done 事件回来才更新，两个条件一起等
  await page.waitForFunction(
    () =>
      document.querySelectorAll('.chat__item').length === 2 &&
      (document.querySelector('.chat__item-title')?.textContent ?? '').includes('第二段对话'),
    { timeout: 30000 },
  )
})

// 用页面上的删除按钮清掉当前会话（顺带验证删除交互），其余交给接口清理
await step('UI-09 会话删除需二次确认', async () => {
  // 会话项的操作收进「...」菜单：hover 出按钮，再点开菜单
  await page.waitForSelector('.chat__item-actions', { visible: true })
  await page.hover('.chat__item')
  // hover 之后按钮才从 opacity 0 显现，等一拍再点，否则点到的是隐藏态
  await new Promise((resolve) => setTimeout(resolve, 250))
  await page.click('.chat__item-actions button')
  await new Promise((resolve) => setTimeout(resolve, 400))

  // 每个会话项都有自己的「...」菜单，关着的那几个也在 DOM 里；
  // 只对当前可见的那一项动手，否则会点到隐藏菜单上。
  const targets = await page.$$('.my-menu__item')
  let clicked = false
  for (const item of targets) {
    const text = (await item.evaluate((el) => el.textContent?.trim())) ?? ''
    if (text !== '删除') continue
    if (!(await item.isIntersectingViewport())) continue
    await item.click()
    clicked = true
    break
  }
  if (!clicked) throw new Error('没找到可见的「删除」菜单项')

  await page.waitForSelector('.my-box', { visible: true })
  await page.click('.my-box .my-box__btn--primary')
  await page.waitForFunction(() => document.querySelectorAll('.chat__item').length === 1, {
    timeout: 5000,
  })
})

await cleanAll()
const left = (await (await api('/api/conversations')).json()).data.total
console.log('leftover conversations:', left)

console.log('console errors:', errors.length ? errors : 'none')
await browser.close()

await browser.close()
console.log(`\n${failures === 0 ? '全部通过' : failures + ' 项失败'}；截图：${OUT}/chat-page.png`)
process.exit(failures === 0 ? 0 : 1)
