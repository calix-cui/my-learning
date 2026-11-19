/**
 * 执行与连接解耦的真实联调：真实 Chrome + 真实后端 + 真实模型。
 *
 * 跑法：BASE=http://127.0.0.1:5199 pnpm acceptance:live
 * 前置：后端跑在 8000（含真实模型配置），vite dev 在 5199 且代理 /api → 8000。
 *
 * 与前几个验收脚本的区别：这里不拦任何请求，模型调用、落库、断流都是真的。
 * 验证的是两件用户真正会遇到的事：
 * A. 刷新页面之后，后端那条回复**继续生成**，回来还能接着看（以前会被直接掐死）；
 * B. 用户点「停止」才停，已生成的部分留下、标注被终止，并能一键重新生成。
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
const LONG_QUESTION = '请写一篇 1500 字左右的短篇小说开头，只输出正文。'

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
          resolve({ status: res.statusCode, body: parsed, raw: text })
        })
      },
    )
    req.on('error', reject)
    if (payload) req.write(payload)
    req.end()
  })
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

/** 等某个条件成立，超时就带着页面现场报错 */
async function waitFor(page, fn, timeout, label) {
  const deadline = Date.now() + timeout
  while (Date.now() < deadline) {
    if (await page.evaluate(fn)) return true
    await sleep(500)
  }
  const dump = await page.evaluate(() => document.body.innerText.slice(0, 600))
  throw new Error(`等待「${label}」超时，当前页面：\n${dump}`)
}

/** 输入并发送：先等输入区可交互，再等发送键真的能点（技能目录没加载完时它是禁用的） */
async function send(page, text) {
  await page.waitForSelector('textarea[aria-label="消息内容"]:not([disabled])', { timeout: 30000 })
  await page.click('textarea[aria-label="消息内容"]')
  await page.type('textarea[aria-label="消息内容"]', text)
  await page.waitForSelector('button[aria-label="发送"]:not([disabled])', { timeout: 30000 })
  await page.click('button[aria-label="发送"]')
}

/** 等这次运行真的在页面上跑起来：停止键或流式气泡出现 */
async function waitRunning(page, timeout) {
  const deadline = Date.now() + timeout
  while (Date.now() < deadline) {
    const state = await page.evaluate(() => ({
      stop: Boolean(document.querySelector('button[aria-label="停止"]')),
      streaming: Boolean(document.querySelector('.chat__bubble--streaming')),
    }))
    if (state.stop || state.streaming) return state
    await sleep(300)
  }
  return { stop: false, streaming: false }
}

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

  const pageErrors = []
  page.on('pageerror', (error) => pageErrors.push(String(error)))
  const httpErrors = []
  const serverErrors = []
  page.on('response', async (res) => {
    if (res.status() >= 400) httpErrors.push(`${res.status()} ${res.url()}`)
    if (res.status() >= 500) {
      // 5xx 要留下响应体，否则只能看到「有个 500」而不知道是哪一步炸的
      const body = await res.text().catch(() => '')
      serverErrors.push(`${res.status()} ${res.url()} ${body.slice(0, 200)}`)
    }
  })
  const requests = []
  page.on('request', (req) => {
    if (req.method() === 'POST' && req.url().includes('/messages/stream')) requests.push('stream')
    if (req.method() === 'POST' && req.url().includes('/regenerate')) requests.push('regenerate')
    if (req.method() === 'POST' && req.url().includes('/stop')) requests.push('stop')
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

    const cookies = await page.cookies()
    const cookie = cookies.map((item) => `${item.name}=${item.value}`).join('; ')

    // ---- 场景 A：跑到一半刷新页面，后端继续跑 ----
    await send(page, QUESTION)
    const running = await waitRunning(page, 20000)
    check('运行中发送键变成停止', running.stop, JSON.stringify(running))
    await page.reload({ waitUntil: 'domcontentloaded' })
    check('刷新页面（用户最常见的断流动作）', true)

    const seen = []
    for (let index = 0; index < 8; index += 1) {
      await sleep(700)
      const snapshot = await page.evaluate(() => ({
        text: document.body.innerText,
        streaming: document.body.innerText.includes('停止'),
      }))
      seen.push(snapshot.text.length)
      if (snapshot.streaming === false && snapshot.text.length > 0 && index > 1) break
    }
    check('刷新后界面立刻有内容，不是一片空白', seen[0] > 0, `首帧 ${seen[0]} 字符`)
    check(
      '刷新后没有把运行判死（不出现「执行尚未结束，连接已中断」的终态）',
      !(await page.evaluate(() => document.body.innerText.includes('执行尚未结束'))),
    )

    const conversations = await request('GET', '/api/conversations?page=1&page_size=10', { cookie })
    const conversationId = conversations.body?.data?.items?.[0]?.id
    let run = null
    const deadline = Date.now() + 180000
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
    check('服务端把这次运行跑完，不是被中断', run?.status === 'completed', `status=${run?.status}`)
    check('没有失败原因', !run?.error_message, String(run?.error_message ?? ''))

    await waitFor(
      page,
      () => document.body.innerText.includes('243'),
      60000,
      '正文里出现答案',
    )
    check('刷新后正文继续长出来，答案完整', true)
    check('只提交过一次', requests.filter((item) => item === 'stream').length === 1)
    check(
      '刷新没有再触发一次提交',
      requests.filter((item) => item === 'stream').length === 1,
      requests.join(','),
    )
    await page.screenshot({ path: `${OUT}/live-resumed.png` })

    // ---- 场景 B：用户主动停止，已生成的部分留下 ----
    await send(page, LONG_QUESTION)
    const stopping = await waitRunning(page, 20000)
    check('生成过程中能点到停止', stopping.stop, JSON.stringify(stopping))
    // 停止键会在「发送 → 停止」之间被 Vue 重渲染替换掉，用 Puppeteer 的
    // 元素句柄点容易点到已经换下来的旧节点，所以每轮重新查一次，直到请求真的发出。
    for (let attempt = 0; attempt < 12; attempt += 1) {
      await page.evaluate(() => {
        const button = document.querySelector('button[aria-label="停止"]')
        if (button instanceof HTMLElement) button.click()
      })
      await sleep(300)
      if (requests.includes('stop')) break
    }
    check('点了停止之后请求真的发出去了', requests.includes('stop'), requests.join(','))
    await sleep(2000)
    await page.waitForSelector('.chat__execution-stopped', { timeout: 20000 })
    const stopped = await page.$eval('.chat__execution-stopped', (node) => node.innerText)
    check('停止后标注「您终止了此次会话」', stopped.includes('您终止了此次会话'), stopped)
    const draft = await page.$eval('textarea[aria-label="消息内容"]', (node) => node.value)
    check('终止之后输入框不再留着这句话', draft === '', JSON.stringify(draft))

    const afterStop = await request(
      'GET',
      `/api/conversations/${conversationId}?message_limit=50`,
      { cookie },
    )
    const cancelled = (afterStop.body?.data?.runs ?? []).find((item) => item.status === 'cancelled')
    check('服务端记成 cancelled', Boolean(cancelled), `status=${cancelled?.status}`)
    check(
      '终止原因记成 user_cancelled',
      cancelled?.stop_reason === 'user_cancelled',
      String(cancelled?.stop_reason),
    )
    const kept = (afterStop.body?.data?.messages ?? []).filter(
      (message) => message.role === 'assistant',
    )
    check('已生成的部分没有丢', kept.length >= 1, `助手消息 ${kept.length} 条`)
    await page.screenshot({ path: `${OUT}/live-stopped.png` })

    // ---- 场景 C：重新生成 ----
    await page.evaluate(() => {
      const button = [...document.querySelectorAll('.chat__execution-stopped button')].find(
        (item) => item.textContent?.includes('重新生成'),
      )
      button?.click()
    })
    await waitFor(
      page,
      () => !document.body.innerText.includes('您终止了此次会话'),
      30000,
      '旧回答被换掉',
    )
    check('重新生成后旧的终止标记消失', true)
    check(
      '重新生成只调一次接口',
      requests.filter((item) => item === 'regenerate').length === 1,
      requests.join(','),
    )

    const finalDetail = await request(
      'GET',
      `/api/conversations/${conversationId}?message_limit=50`,
      { cookie },
    )
    const finalRuns = finalDetail.body?.data?.runs ?? []
    check('重新生成开了一次新运行', finalRuns.length >= 2, `runs=${finalRuns.length}`)

    // ---- 场景 D：写操作要审批，批准之后真的执行 ----
    // 用真实模型走完整条链：模型请求工具 → 后端挂起 → 卡片 → 批准 → 恢复执行 → 落库。
    await send(page, '把这个会话重命名为「联调改名」，只调用工具，不要解释')
    await page.waitForSelector('.approval', { timeout: 60000 })
    const card = await page.$eval('.approval', (node) => node.innerText)
    check('写操作弹出审批卡片', card.includes('需要你确认'), card.split('\n')[0])
    check('卡片上写明要调用的工具', card.includes('rename_conversation'), card)

    // 卡片刚出现时可能还在核对（按钮 disabled），等它真的可点再点
    await page.waitForFunction(
      () => {
        const button = document.querySelector('.approval__btn--primary')
        return button instanceof HTMLButtonElement && !button.disabled
      },
      { timeout: 30000 },
    )
    await page.click('.approval__btn--primary')
    await waitFor(page, () => !document.querySelector('.approval'), 60000, '审批后卡片收起')
    check('批准之后卡片收起', true)

    // 等运行真的跑完（模型拿到工具结果还要再说一句）
    await waitFor(
      page,
      () => !document.querySelector('button[aria-label="停止"]'),
      60000,
      '审批后运行结束',
    )
    const approved = await request(
      'GET',
      `/api/conversations/${conversationId}?message_limit=50`,
      { cookie },
    )
    const approvedRun = (approved.body?.data?.runs ?? []).find(
      (item) => item.status === 'completed' && item.id > (cancelled?.id ?? 0),
    )
    check('批准之后运行跑完', Boolean(approvedRun), `run=${approvedRun?.id} ${approvedRun?.status}`)
    const renamed = await request('GET', `/api/conversations/${conversationId}`, { cookie })
    check(
      '工具真的执行了：会话改名生效',
      renamed.body?.data?.title === '联调改名',
      String(renamed.body?.data?.title),
    )
    const approvalList = approvedRun
      ? await request('GET', `/api/agent/runs/${approvedRun.id}/approvals`, { cookie })
      : { body: null }
    const decided = (approvalList.body?.data?.items ?? [])[0]
    check(
      '审批记录记成 approved',
      decided?.status === 'approved',
      `${decided?.tool_name} ${decided?.status}`,
    )

    const steps = approvedRun
      ? await request('GET', `/api/agent/runs/${approvedRun.id}/steps`, { cookie })
      : { body: null }
    const items = steps.body?.data?.items ?? []
    const callStep = items.find((item) => item.kind === 'tool_call')
    const resultStep = items.find((item) => item.kind === 'tool_result')
    check(
      '步骤按 call_id 配对，而不是靠名字',
      Boolean(callStep?.call_id) && callStep.call_id === resultStep?.call_id,
      `${callStep?.call_id} / ${resultStep?.call_id}`,
    )
    await page.screenshot({ path: `${OUT}/live-approval.png` })

    check('页面没有未捕获异常', pageErrors.length === 0, pageErrors.slice(0, 2).join(' | '))
    check('没有 5xx 响应', serverErrors.length === 0, serverErrors.slice(0, 2).join(' | '))
  } finally {
    await browser.close()
  }

  const failed = checks.filter((item) => !item.passed)
  await fs.writeFile(
    `${OUT}/live-report.json`,
    JSON.stringify({ base: BASE, api: API, email: EMAIL, checks, failed: failed.length }, null, 2),
  )
  console.log(`\n${checks.length - failed.length}/${checks.length} 项通过（真实模型）`)
  if (failed.length) process.exitCode = 1
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
