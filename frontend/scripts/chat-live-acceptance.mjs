/**
 * 第五步「断线核对」真实联调：真实 Chrome + 真实后端 + 真实模型。
 *
 * 跑法：BASE=http://127.0.0.1:5199 pnpm acceptance:live
 * 前置：后端跑在 8000（含真实 DeepSeek 配置），vite dev 在 5199 且代理 /api → 8000。
 *
 * 与前两个验收脚本的区别：这里不拦任何请求，模型调用、落库、断流都是真的。
 * 验证的是用户真正会遇到的那件事——网断了以后，能不能知道那条消息怎么了。
 */
import http from 'node:http'
import fs from 'node:fs/promises'
import puppeteer from 'puppeteer-core'

const BASE = process.env.BASE ?? 'http://127.0.0.1:5199'
const API = process.env.API ?? 'http://127.0.0.1:8000'
const OUT = process.env.OUT ?? '.acceptance'
const CHROME =
  process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

const STAMP = Date.now()
const EMAIL = `live-${STAMP}@example.com`
const PASSWORD = 'live-check-123'
const QUESTION = '用计算器算出 3 的 5 次方，然后一句话告诉我结果'

const checks = []
function check(name, passed, detail = '') {
  checks.push({ name, passed: Boolean(passed), detail: String(detail) })
  console.log(`[${passed ? 'ok' : 'FAIL'}] ${name}${detail ? `：${detail}` : ''}`)
}

/** 直接走 node:http，绕开环境里的 http_proxy（它会让 fetch 解析地址失败） */
function request(method, path, { body, cookie } = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, API)
    const payload = body === undefined ? null : JSON.stringify(body)
    const headers = {}
    if (payload) {
      headers['Content-Type'] = 'application/json'
      headers['Content-Length'] = Buffer.byteLength(payload)
    }
    if (cookie) headers.Cookie = cookie
    const req = http.request(
      { hostname: url.hostname, port: url.port, path: url.pathname + url.search, method, headers },
      (res) => {
        let text = ''
        res.setEncoding('utf8')
        res.on('data', (chunk) => (text += chunk))
        res.on('end', () => {
          let parsed = null
          try {
            parsed = JSON.parse(text)
          } catch {
            // 非 JSON 响应（例如健康检查）按 null 处理
          }
          resolve({ status: res.statusCode, body: parsed, raw: text, headers: res.headers })
        })
      },
    )
    req.on('error', reject)
    if (payload) req.write(payload)
    req.end()
  })
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function main() {
  await fs.mkdir(OUT, { recursive: true })

  const registered = await request('POST', '/api/auth/register', {
    body: { email: EMAIL, password: PASSWORD, display_name: '联调账号' },
  })
  check('后端可用，账号已建', registered.status === 200, `HTTP ${registered.status}`)

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  })
  const page = await browser.newPage()
  await page.setViewport({ width: 1440, height: 900 })

  // 登录前探测 /auth/me 必然 401，那是正常的；只收集真正的未捕获异常与 5xx
  const pageErrors = []
  page.on('pageerror', (error) => pageErrors.push(String(error)))

  const httpErrors = []
  page.on('response', (res) => {
    const status = res.status()
    if (status >= 400) httpErrors.push(`${status} ${res.request().method()} ${res.url()}`)
  })

  const streams = []
  page.on('request', (req) => {
    if (req.method() === 'POST' && req.url().includes('/messages/stream')) streams.push(req.url())
  })

  try {
    await page.goto(`${BASE}/chat`, { waitUntil: 'networkidle2' })
    await page.waitForSelector('input[type="email"]', { timeout: 15000 })
    await page.type('input[type="email"]', EMAIL)
    await page.type('input[type="password"]', PASSWORD)
    await Promise.all([
      page.waitForSelector('textarea[aria-label="消息内容"]', { timeout: 20000 }),
      page.click('button.auth__submit'),
    ])
    check('真实账号登录成功，进入对话页', true, page.url())

    await page.type('textarea[aria-label="消息内容"]', QUESTION)
    await page.click('button[aria-label="发送"]')

    // 等流真的开起来，再刷新页面：这是用户最常做的事，也真的会掐断 SSE
    await page.waitForFunction(
      () =>
        Boolean(
          document.querySelector(
            '.chat__scroll .chat__row, .chat__scroll details.timeline, .chat__bubble--streaming',
          ),
        ),
      { timeout: 20000 },
    )
    await sleep(800)
    await page.reload({ waitUntil: 'domcontentloaded' })
    check('刷新页面掐断 SSE（用户最常见的断流动作）', true)

    try {
      await page.waitForFunction(
        () => {
          const banner = document.querySelector('.chat__recovery')
          return banner && banner.textContent.includes('连接已中断')
        },
        { timeout: 30000 },
      )
    } catch (error) {
      const dump = await page.evaluate(() => document.body.innerText)
      console.log('--- 页面正文 ---\n' + dump.slice(0, 800))
      throw error
    }
    const bannerText = await page.$eval('.chat__recovery', (el) => el.textContent.trim())
    check('断流后出现恢复提示', bannerText.includes('连接已中断'), bannerText.slice(0, 40))

    const locked = await page.$eval('button[aria-label="发送"]', (el) => el.disabled)
    check('断流后锁住发送', locked)
    check('只发过 1 次提交', streams.length === 1, `${streams.length} 次`)

    // 从浏览器拿会话 cookie，直接查后端：真实链路里运行最终会是什么状态
    const cookies = await page.cookies()
    const cookie = cookies.map((item) => `${item.name}=${item.value}`).join('; ')
    const conversations = await request('GET', '/api/conversations?page=1&page_size=10', { cookie })
    const conversationId = conversations.body?.data?.items?.[0]?.id
    check('能读到会话', Boolean(conversationId), `id=${conversationId}`)

    let run = null
    const deadline = Date.now() + 150000
    while (Date.now() < deadline) {
      const detail = await request(
        'GET',
        `/api/conversations/${conversationId}?message_limit=50`,
        { cookie },
      )
      run = detail.body?.data?.runs?.[0] ?? null
      if (run && run.status !== 'running') break
      await sleep(2000)
    }
    check('服务端把断掉的运行收尾成终态', run?.status !== 'running', `status=${run?.status}`)
    check(
      '服务端记下了失败原因',
      run?.error_message === '运行被中断',
      String(run?.error_message),
    )

    await page.setOfflineMode(false)
    await page.click('.chat__recovery button')
    await page.waitForFunction(
      () => {
        const banner = document.querySelector('.chat__recovery')
        return banner && banner.textContent.includes('运行被中断')
      },
      { timeout: 30000 },
    )
    const afterText = await page.$eval('.chat__recovery', (el) => el.textContent.trim())
    check('核对后把服务端原因显示出来', afterText.includes('运行被中断'), afterText.slice(0, 60))

    // 草稿已在核对时清空，输入框本身应可用；打一个字再看发送键
    await page.type('textarea[aria-label="消息内容"]', '还能再发吗')
    const unlocked = await page.$eval('button[aria-label="发送"]', (el) => !el.disabled)
    await page.$eval('textarea[aria-label="消息内容"]', (el) => {
      el.value = ''
      el.dispatchEvent(new Event('input', { bubbles: true }))
    })
    if (!unlocked) {
      const dump = await page.evaluate(() => ({
        banner: document.querySelector('.chat__recovery')?.textContent?.trim() ?? null,
        textareaDisabled:
          document.querySelector('textarea[aria-label="消息内容"]')?.disabled ?? null,
        rows: document.querySelectorAll('.chat__scroll .chat__row').length,
        text: document.body.innerText.slice(0, 400),
      }))
      console.log('--- 仍未解锁时的页面状态 ---\n' + JSON.stringify(dump, null, 2))
    }
    check('核对后发送恢复可用', unlocked)
    check('核对不重发（仍只有 1 次提交）', streams.length === 1, `${streams.length} 次`)
    const serverErrors = httpErrors.filter((item) => !item.startsWith('401'))
    check('页面没有未捕获异常', pageErrors.length === 0, pageErrors.slice(0, 2).join(' | '))
    check('没有 5xx 响应', serverErrors.length === 0, serverErrors.slice(0, 2).join(' | '))
    console.log('--- 4xx/5xx 请求 ---\n' + (httpErrors.join('\n') || '（无）'))

    await page.screenshot({ path: `${OUT}/live-interrupted.png` })
  } finally {
    await browser.close()
  }

  const failed = checks.filter((item) => !item.passed)
  await fs.writeFile(
    `${OUT}/live-report.json`,
    JSON.stringify(
      { base: BASE, api: API, email: EMAIL, conversationId: null, checks, failed: failed.length },
      null,
      2,
    ),
  )
  console.log(`\n${checks.length - failed.length}/${checks.length} 项通过（真实模型）`)
  if (failed.length) process.exitCode = 1
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
