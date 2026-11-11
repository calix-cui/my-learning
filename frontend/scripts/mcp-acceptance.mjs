/**
 * 阶段 7「MCP 工具市场」端到端验收：真实浏览器 + 真实后端 + 真的 stdio MCP 服务器。
 *
 * 跑法：BASE=http://127.0.0.1:5173 pnpm acceptance:mcp
 *
 * 覆盖两条链路：
 * 1) 市场页：浏览 → 自定义接入 → 自动试连 → 看工具清单 → 启停 → 移除；
 * 2) 审批链：用 `backend/scripts/seed_mcp_approval.py` 造一条「卡在审批上」的 run
 *    （不赌模型这次肯不肯调工具），前端点批准后走真实链路真的执行一次 MCP 调用。
 */
import { execFileSync } from 'node:child_process'
import fs from 'node:fs/promises'
import path from 'node:path'
import puppeteer from 'puppeteer-core'

const BASE = process.env.BASE ?? 'http://127.0.0.1:5173'
const OUT = process.env.OUT ?? '.acceptance'
const CHROME =
  process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const BACKEND = path.resolve(process.cwd(), '..', 'backend')

await fs.mkdir(OUT, { recursive: true })

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu', '--user-data-dir=/tmp/cp-mcp-e2e'],
})
const page = await browser.newPage()
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })

const errors = []
page.on('console', (message) => {
  const text = message.text()
  if (message.type() === 'error' && !text.includes('401')) errors.push(text)
})
page.on('pageerror', (error) => errors.push(String(error)))

const email = `mcp-e2e-${Date.now()}@example.com`
const registerResponse = await fetch(`${BASE}/api/auth/register`, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ email, password: 'password123' }),
})
if (!registerResponse.ok) {
  throw new Error(`注册失败：${registerResponse.status} ${await registerResponse.text()}`)
}
const cookie = registerResponse.headers
  .getSetCookie()
  .map((item) => item.split(';')[0])
  .find((item) => item.startsWith('my_agent_session='))
if (!cookie) throw new Error('注册响应没有下发 my_agent_session Cookie')

const api = async (path, init = {}) => {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'content-type': 'application/json', ...(init.headers ?? {}), cookie },
  })
  const text = await response.text()
  return { status: response.status, body: text ? JSON.parse(text) : null }
}

let failures = 0
const step = async (name, fn) => {
  try {
    const value = await fn()
    console.log('PASS', name)
    return value
  } catch (error) {
    failures += 1
    console.log('FAIL', name, '-', error.message)
    return undefined
  }
}

const goto = async (url) => {
  await page.goto(url, { waitUntil: 'networkidle2' })
  await page.evaluate(() => document.getElementById('__vue-devtools-container__')?.remove())
}

/** 带默认值的输入要先清空再打字，否则会拼成 uvxuv */
const fill = async (selector, text) => {
  await page.click(selector, { clickCount: 3 })
  await page.keyboard.press('Backspace')
  await page.type(selector, text)
}

const clickByText = async (selector, text) => {
  for (const handle of await page.$$(selector)) {
    const content = await handle.evaluate((el) => el.textContent?.trim() ?? '')
    if (content === text) {
      await handle.click()
      return
    }
  }
  throw new Error(`找不到 ${selector} 里文字为「${text}」的元素`)
}

/** 市场页的数据是异步拉的，等卡片出现再断言，不然读到的是空网格 */
const waitMarket = async () => {
  await page.waitForSelector('.market__grid', { timeout: 20000 })
  await page.waitForSelector('.market__card', { timeout: 30000 })
}

const marketCards = () => page.$$eval('.market__card', (nodes) => nodes.length)
const serverCards = () =>
  page.$$eval('.market__card', (nodes) =>
    nodes
      .filter((node) => node.querySelector('.market__status'))
      .map((node) => ({
        name: node.querySelector('.market__name')?.textContent?.trim() ?? '',
        status: node.querySelector('.market__status')?.textContent?.trim() ?? '',
        count: node.querySelector('.market__count')?.textContent?.trim() ?? '',
      })),
  )

const installEcho = async () => {
  const response = await api('/api/mcp/servers', {
    method: 'POST',
    body: JSON.stringify({
      slug: 'echo',
      display_name: '回显测试',
      transport: 'stdio',
      command: 'uv',
      args: ['run', '--no-sync', 'python', 'tests/fixtures/mcp_echo_server.py'],
    }),
  })
  if (response.status !== 200) throw new Error(`接入失败：${JSON.stringify(response.body)}`)
  return response.body.data
}

await goto(`${BASE}/login`)
await page.type('.auth__card input[type="email"]', email)
await page.type('.auth__card input[type="password"]', 'password123')
await Promise.all([
  page.waitForResponse((response) => response.url().includes('/api/auth/login')),
  page.click('.auth__card .el-button'),
])
await page.waitForSelector('.chat__bar, .chat__empty-title', { timeout: 20000 })

await goto(`${BASE}/chat?settings=1`)
await page.waitForSelector('.settings-window', { timeout: 20000 })
await clickByText('.settings__item', '工具市场')
await waitMarket()

await step('M-01 市场页列出内置条目与四种筛选', async () => {
  const cards = await marketCards()
  if (cards < 7) throw new Error(`内置条目只有 ${cards} 张卡`)
  const chips = await page.$$eval('.market__chip', (nodes) =>
    nodes.map((node) => node.textContent?.trim()),
  )
  const expected = ['全部', '已接入', '本地', '远程']
  if (chips.join(',') !== expected.join(',')) throw new Error(`筛选不对：${chips.join(',')}`)
})

await step('M-02 筛选「远程」只剩远程服务', async () => {
  await clickByText('.market__chip', '远程')
  await new Promise((resolve) => setTimeout(resolve, 300))
  const names = await page.$$eval('.market__name', (nodes) =>
    nodes.map((node) => node.textContent?.trim()),
  )
  if (names.length !== 1 || names[0] !== 'DeepWiki') throw new Error(`远程条目：${names.join(',')}`)
  await clickByText('.market__chip', '全部')
})

await step('M-03 自定义接入后自动试连并显示「正常」', async () => {
  await clickByText('.market__custom', '自定义接入')
  await page.waitForSelector('.market__form')
  await page.type('#mcp-slug', 'echo')
  await page.type('#mcp-display-name', '回显测试')
  await fill('#mcp-command', 'uv')
  await fill('#mcp-args', 'run --no-sync python tests/fixtures/mcp_echo_server.py')
  const [response] = await Promise.all([
    page.waitForResponse((item) => item.url().endsWith('/api/mcp/servers'), { timeout: 30000 }),
    clickByText('.market__form .market__cta', '接入'),
  ])
  if (response.status() !== 200) {
    throw new Error(`接入接口返回 ${response.status()}：${await response.text()}`)
  }
  await page.waitForFunction(
    () =>
      [...document.querySelectorAll('.market__status')].some(
        (node) => node.textContent?.trim() === '正常',
      ),
    { timeout: 90000 },
  )
  const servers = await serverCards()
  const echo = servers.find((item) => item.name === '回显测试')
  if (!echo) throw new Error('没找到「回显测试」卡片')
  if (!echo.count.includes('2 个工具')) throw new Error(`工具数不对：${echo.count}`)
})

await step('M-04 点工具数能展开真实的工具名', async () => {
  await page.click('.market__count--link')
  await page.waitForSelector('.market__tools', { timeout: 60000 })
  const names = await page.$$eval('.market__tool-name', (nodes) =>
    nodes.map((node) => node.textContent?.trim()),
  )
  for (const expected of ['mcp__echo__echo', 'mcp__echo__add']) {
    if (!names.includes(expected)) throw new Error(`清单里没有 ${expected}：${names.join(',')}`)
  }
  await page.screenshot({ path: `${OUT}/mcp-01-market.png` })
})

await step('M-05 「工具」节里能看到 MCP 工具且标为需确认', async () => {
  await clickByText('.settings__item', '工具')
  await page.waitForSelector('.tools__row', { timeout: 30000 })
  const rows = await page.$$eval('.tools__row', (nodes) =>
    nodes.map((node) => ({
      text: node.textContent ?? '',
      name: node.querySelector('.tools__name')?.textContent?.trim() ?? '',
    })),
  )
  const echo = rows.find((row) => row.name === 'mcp__echo__echo')
  if (!echo) throw new Error(`工具节没有 mcp__echo__echo：${rows.map((r) => r.name).join(',')}`)
  if (!echo.text.includes('需确认')) throw new Error('MCP 工具没有标「需确认」')
})

await step('M-06 关掉服务器后工具从模型可见列表里消失', async () => {
  const list = await api('/api/mcp/servers')
  const server = list.body.data.items.find((item) => item.slug === 'echo')
  const disabled = await api(`/api/mcp/servers/${server.id}`, {
    method: 'PATCH',
    body: JSON.stringify({ enabled: false }),
  })
  if (disabled.status !== 200) throw new Error(`关停失败：${JSON.stringify(disabled.body)}`)
  const tools = await api('/api/settings/tools')
  const names = tools.body.data.items.map((item) => item.name)
  if (names.includes('mcp__echo__echo')) throw new Error('关掉后工具还在清单里')
  const enabled = await api(`/api/mcp/servers/${server.id}`, {
    method: 'PATCH',
    body: JSON.stringify({ enabled: true }),
  })
  if (enabled.status !== 200) throw new Error('重新启用失败')
})

await step('M-07 移除后市场回到未接入状态', async () => {
  await clickByText('.settings__item', '工具市场')
  await waitMarket()
  await page.click('.market__mini.is-danger')
  await page.waitForSelector('.my-box', { visible: true, timeout: 10000 })
  await clickByText('.my-box__btn--primary', '移除')
  await page.waitForSelector('.my-box', { hidden: true, timeout: 10000 })
  await page.reload({ waitUntil: 'networkidle2' })
  await clickByText('.settings__item', '工具市场')
  await waitMarket()
  const servers = await serverCards()
  if (servers.length) throw new Error(`刷新后仍有 ${servers.length} 台已接入`)
})

// 审批链：重新接一台 echo，再造一条卡在审批上的 run
await step('M-08 造一条等待审批的 run 并出现审批卡', async () => {
  await installEcho()
  const raw = execFileSync(
    'uv',
    [
      'run',
      '--no-sync',
      'python',
      'scripts/seed_mcp_approval.py',
      '--email',
      email,
      '--server-slug',
      'echo',
      '--text',
      '你好，MCP',
    ],
    { cwd: BACKEND, encoding: 'utf8', env: { ...process.env, UV_CACHE_DIR: '/tmp/uvcache' } },
  )
  const line = raw.trim().split('\n').pop() ?? ''
  const info = JSON.parse(line)

  await goto(`${BASE}/chat`)
  await page.waitForSelector('.chat__item', { timeout: 20000 })
  // 用 API 拿标题后点进那个会话，避免依赖列表顺序
  const detail = await api(`/api/conversations/${info.conversation_id}`)
  const title = detail.body.data.title
  for (const handle of await page.$$('.chat__item-title')) {
    if ((await handle.evaluate((el) => el.textContent?.trim())) === title) {
      await handle.click()
      break
    }
  }
  await page.waitForSelector('.approval', { timeout: 20000 })
  const tool = await page.$eval('.approval__tool', (node) => node.textContent?.trim())
  if (tool !== 'mcp__echo__echo') throw new Error(`审批卡工具名不对：${tool}`)
  await page.screenshot({ path: `${OUT}/mcp-02-approval.png` })
})

await step('M-09 批准后时间线出现真实执行结果', async () => {
  await clickByText('.approval__btn--primary', '批准执行')
  await page.waitForFunction(
    () =>
      [...document.querySelectorAll('.timeline__text')].some((node) =>
        (node.textContent ?? '').includes('你好，MCP'),
      ),
    { timeout: 90000 },
  )
  await page.waitForFunction(() => !document.querySelector('.approval'), { timeout: 30000 })
  await page.screenshot({ path: `${OUT}/mcp-03-approved.png` })
})

await step('M-10 刷新后没有残留审批卡', async () => {
  await page.reload({ waitUntil: 'networkidle2' })
  await page.waitForSelector('.chat__bar, .chat__empty-title', { timeout: 20000 })
  if (await page.$('.approval')) throw new Error('刷新后审批卡还在')
})

await step('M-11 控制台没有报错', async () => {
  if (errors.length) throw new Error(errors.join(' | '))
})

// 清理：把造出来的账号删掉，连带 MCP 服务器和会话
await api('/api/auth/me', { method: 'DELETE', body: JSON.stringify({ password: 'password123' }) })

await browser.close()
console.log(failures === 0 ? '\n全部通过' : `\n${failures} 项失败`)
process.exit(failures === 0 ? 0 : 1)
