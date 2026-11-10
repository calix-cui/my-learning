/**
 * 账号体系端到端验收：注册 → 进对话 → 刷新仍在 → 发消息 → 退出 → 再登录数据还在。
 *
 * 用法（先确保后端 :8000、前端 :5173 都在跑）：
 *   pnpm acceptance:auth
 *   BASE=http://127.0.0.1:5173 OUT=.acceptance pnpm acceptance:auth
 */

import fs from 'node:fs'
import path from 'node:path'

import puppeteer from 'puppeteer-core'

const BASE = process.env.BASE ?? 'http://127.0.0.1:5173'
const OUT = process.env.OUT ?? '.acceptance'
const CHROME =
  process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

const results = []
const email = `e2e-${Date.now()}@example.com`
const password = 'password123'

function check(name, ok, detail = '') {
  results.push({ name, ok, detail })
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`)
}

async function textOf(page) {
  return page.evaluate(() => document.body.innerText)
}

async function waitText(page, needle, timeout = 8000) {
  await page.waitForFunction((t) => document.body.innerText.includes(t), { timeout }, needle)
}

async function currentPath(page) {
  return page.evaluate(() => window.location.pathname)
}

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu', `--user-data-dir=/tmp/cp-auth-${Date.now()}`],
  defaultViewport: { width: 1440, height: 900, deviceScaleFactor: 2 },
})

try {
  fs.mkdirSync(OUT, { recursive: true })
  const page = await browser.newPage()

  // vue-devtools 的悬浮面板固定在页面中央，headless 下会挡住按钮的鼠标点击；
  // 每次导航后移除它（插件本身只在 dev 注入，不影响产物）。
  const gotoPage = async (url) => {
    await page.goto(url, { waitUntil: 'networkidle2' })
    await page
      .evaluate(() => document.getElementById('__vue-devtools-container__')?.remove())
      .catch(() => undefined)
  }

  const consoleErrors = []
  page.on('console', (msg) => {
    // 浏览器会把 404/401 的资源加载失败也记为 console error，下面的 response 监听已单独统计
    if (msg.type() === 'error' && !msg.text().includes('Failed to load resource')) {
      consoleErrors.push(msg.text())
    }
  })
  const unexpectedStatuses = []
  page.on('response', (response) => {
    const { status } = response
    const url = response.url()
    // 允许：favicon 缺失；启动时 /auth/me 的 401（未登录探测的正常结果）
    if (url.endsWith('/favicon.ico')) return
    if (url.includes('/api/auth/me') && status === 401) return
    if (status >= 400) unexpectedStatuses.push(`${status} ${url}`)
  })

  // 1. 未登录访问根路径 → 登录页
  await gotoPage(`${BASE}/`)
  await waitText(page, '登录')
  check(
    '未登录访问 / 会被送到登录页',
    (await currentPath(page)) === '/login',
    await currentPath(page),
  )

  // 2. 未登录直接访问 /chat → 也回登录页，并带上 redirect
  await gotoPage(`${BASE}/chat`)
  await waitText(page, '登录')
  const loginUrl = page.url()
  check(
    '未登录访问 /chat 带 redirect 参数',
    (await currentPath(page)) === '/login' && loginUrl.includes('redirect='),
    loginUrl,
  )
  await page.screenshot({ path: path.join(OUT, 'auth-01-login.png') })

  // 3. 去注册 → 自动登录 → 进入对话页
  await page.click('.auth__switch a')
  await waitText(page, '创建账号后即可开始对话')
  const inputs = await page.$$('.auth__card input')
  await inputs[0].type(email)
  await inputs[1].type(password)
  await inputs[2].type(password)
  await page.screenshot({ path: path.join(OUT, 'auth-02-register.png') })
  await page.click('.auth__submit')
  await waitText(page, '新建会话', 12000)
  check('注册成功后落在对话页', (await currentPath(page)) === '/chat', await currentPath(page))

  const bodyAfterRegister = await textOf(page)
  check('顶栏显示当前用户邮箱', bodyAfterRegister.includes(email))

  // 4. 刷新后仍然登录（会话 Cookie 生效）
  await page.reload({ waitUntil: 'networkidle2' })
  await waitText(page, '新建会话')
  check('刷新后仍处于登录态', (await currentPath(page)) === '/chat', await currentPath(page))

  // 5. 新建会话并发一条消息，拿到回复
  await page.click('.chat__new')
  await page.waitForSelector('.chat__empty-title', { timeout: 8000 })
  const box = await page.$('.chat__composer textarea')
  await box.type('你好，我是端到端测试')
  await page.keyboard.press('Enter')
  // 等助手气泡出现（真实模型与 fake 模型的回复内容不同，只数气泡）
  await page.waitForSelector('.chat__row--assistant', { timeout: 30000 })
  await page.waitForFunction(
    () => !document.querySelector('.chat__composer .el-button.is-loading'),
    { timeout: 30000 },
  )
  const assistantText = await page.$eval('.chat__row--assistant .chat__content', (el) =>
    el.textContent?.trim(),
  )
  check(
    '发送消息并收到回复',
    Boolean(assistantText && assistantText.length > 0),
    assistantText?.slice(0, 30),
  )
  await page.screenshot({ path: path.join(OUT, 'auth-03-chat.png') })

  const conversationTitle = await page.$eval('.chat__item--active .chat__item-title', (el) =>
    el.textContent.trim(),
  )

  // 6. 退出登录 → 回登录页，且再访问 /chat 进不去
  await page.click('.layout__user-trigger')
  await page.waitForSelector('.my-menu__item', { timeout: 5000 })
  await page.evaluate(() => {
    const items = [...document.querySelectorAll('.my-menu__item')]
    const target = items.find((el) => el.textContent?.includes('退出登录'))
    target?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  })
  // 菜单里也有「退出登录」四个字，等文字会立刻命中；直接等路由
  await page.waitForFunction(() => location.pathname === '/login', { timeout: 10000 })
  check('退出登录后回到登录页', (await currentPath(page)) === '/login', await currentPath(page))

  await gotoPage(`${BASE}/chat`)
  await waitText(page, '登录')
  check('退出后无法再访问 /chat', (await currentPath(page)) === '/login', await currentPath(page))

  // 7. 重新登录 → 之前的会话与消息都还在
  const loginInputs = await page.$$('.auth__card input')
  await loginInputs[0].type(email)
  await loginInputs[1].type(password)
  await page.click('.auth__submit')
  await page.waitForSelector('.chat__item', { timeout: 15000 })
  // 侧边栏标题有省略号，innerText 会被截断，这里读 textContent 做完整比对
  const titles = await page.$$eval('.chat__item-title', (els) =>
    els.map((el) => el.textContent?.trim() ?? ''),
  )
  check('重新登录后原有会话仍在列表里', titles.includes(conversationTitle), titles.join(' / '))
  // 重新登录后应用不会自动选中会话，点开第一条再看历史
  await page.click('.chat__item')
  await page.waitForSelector('.chat__row--assistant', { timeout: 15000 })
  const replyStillThere = await page.$eval(
    '.chat__row--assistant .chat__content',
    (el) => el.textContent?.trim() ?? '',
  )
  check('重新登录后消息历史仍在', replyStillThere.length > 0, replyStillThere.slice(0, 20))
  await page.screenshot({ path: path.join(OUT, 'auth-04-relogin.png') })

  // 8. 会话 Cookie 必须是 HttpOnly（前端 JS 读不到）
  const cookieVisible = await page.evaluate(() => document.cookie.includes('my_agent_session'))
  check('会话 Cookie 对 JS 不可见（HttpOnly）', cookieVisible === false)

  check('控制台无报错', consoleErrors.length === 0, consoleErrors.slice(0, 2).join(' | '))
  check(
    '没有意外的 4xx/5xx 响应',
    unexpectedStatuses.length === 0,
    unexpectedStatuses.slice(0, 2).join(' | '),
  )
} finally {
  await browser.close()
  const failed = results.filter((r) => !r.ok)
  console.log(`\n${results.length - failed.length}/${results.length} passed`)
  fs.writeFileSync(path.join(OUT, 'auth-report.json'), JSON.stringify(results, null, 2))
  if (failed.length > 0) process.exitCode = 1
}
