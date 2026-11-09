import fs from 'node:fs/promises'
import puppeteer from 'puppeteer-core'

/**
 * 设置模块的端到端验收：模型接入 / 账号资料 / 登录设备 / 数据管理。
 *
 *   pnpm acceptance:settings           # 默认打 http://127.0.0.1:5173
 *   BASE=http://127.0.0.1:4173 pnpm acceptance:settings
 *
 * 会注册一个一次性账号，跑完把它注销掉（同时验证注销流程）。
 */

const BASE = process.env.BASE ?? 'http://127.0.0.1:5173'
const OUT = process.env.OUT ?? '.acceptance'
const CHROME =
  process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

const results = []
function record(name, ok, detail = '') {
  results.push({ name, ok, detail })
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`)
}

async function main() {
  await fs.mkdir(OUT, { recursive: true })
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-gpu', `--user-data-dir=/tmp/cp-settings-${Date.now()}`],
  })
  const page = await browser.newPage()
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })
  await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }])

  const consoleErrors = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })
  page.on('pageerror', (error) => consoleErrors.push(String(error)))

  const hideDevtools = () =>
    page.evaluate(() => document.getElementById('__vue-devtools-container__')?.remove())

  const email = `settings-${Date.now()}@example.com`

  // ---- 注册 ----
  await page.goto(`${BASE}/register`, { waitUntil: 'networkidle2' })
  const inputs = await page.$$('.auth__card input')
  await inputs[0].type(email)
  await inputs[1].type('password123')
  await inputs[2].type('password123')
  await page.click('.auth__submit')
  await page.waitForFunction(() => location.pathname === '/chat', { timeout: 15000 })
  record('注册后进入对话页', true)

  // ---- 模型接入：默认继承环境变量 ----
  await page.goto(`${BASE}/settings`, { waitUntil: 'networkidle2' })
  await hideDevtools()
  await page.waitForSelector('.model__seg', { timeout: 10000 })
  const inheritedNote = await page.$eval('.model__notice', (el) => el.textContent ?? '')
  record('新账号提示「用环境变量配置」', inheritedNote.includes('环境变量'), inheritedNote.trim())

  // 切成内置演示并保存
  await page.evaluate(() => {
    const items = [...document.querySelectorAll('.model__seg-item')]
    items.find((item) => item.textContent?.includes('内置演示'))?.click()
  })
  await page.waitForFunction(() => !document.querySelector('#model-base-url'), { timeout: 5000 })
  await page.evaluate(() => {
    const buttons = [...document.querySelectorAll('.model__actions button')]
    buttons.find((button) => button.textContent?.trim() === '保存')?.click()
  })
  await page.waitForFunction(() => !document.querySelector('.model__notice'), { timeout: 10000 })
  record('保存内置演示后不再显示继承提示', true)

  // 测试连接
  await page.evaluate(() => {
    const buttons = [...document.querySelectorAll('.model__actions button')]
    buttons.find((button) => button.textContent?.trim() === '测试连接')?.click()
  })
  await page.waitForSelector('.model__result', { timeout: 15000 })
  const resultText = await page.$eval('.model__result', (el) => el.textContent ?? '')
  record('测试连接返回结果', resultText.length > 0, resultText.trim())
  await page.screenshot({ path: `${OUT}/settings-01-model.png` })

  // 顶栏模型标签跟随设置
  await page.goto(`${BASE}/chat`, { waitUntil: 'networkidle2' })
  await page.waitForFunction(
    () => document.querySelector('.layout__model')?.textContent?.includes('fake'),
    { timeout: 10000 },
  )
  record('顶栏模型标签变成 fake', true)

  // 内置演示下发消息，应拿到 [fake] 回复
  await page.click('.chat__new')
  await page.waitForSelector('.chat__item', { timeout: 10000 })
  await page.type('.chat__composer textarea', '设置验收：内置演示')
  await page.click('.chat__composer .el-button--primary')
  await page.waitForFunction(
    () =>
      document
        .querySelector('.chat__row--assistant .chat__content')
        ?.textContent?.includes('[fake]'),
    { timeout: 20000 },
  )
  record('内置演示回复带 [fake] 前缀', true)

  // ---- 账号资料：改显示名 ----
  await page.goto(`${BASE}/settings`, { waitUntil: 'networkidle2' })
  await hideDevtools()
  await page.evaluate(() => {
    const items = [...document.querySelectorAll('.settings__item')]
    items.find((item) => item.textContent?.includes('账号资料'))?.click()
  })
  await page.waitForSelector('.account', { timeout: 5000 })
  const nameInput = await page.$('.account__row input')
  await nameInput.click({ clickCount: 3 })
  await nameInput.type('验收小张')
  await page.evaluate(() => {
    const buttons = [...document.querySelectorAll('.account__row button')]
    buttons.find((button) => button.textContent?.trim() === '保存')?.click()
  })
  await page.waitForFunction(
    () => document.querySelector('.layout__user-name')?.textContent?.includes('验收小张'),
    { timeout: 10000 },
  )
  record('显示名保存后侧栏同步', true)
  await page.screenshot({ path: `${OUT}/settings-02-account.png` })

  // ---- 登录设备 ----
  await page.evaluate(() => {
    const items = [...document.querySelectorAll('.settings__item')]
    items.find((item) => item.textContent?.includes('登录设备'))?.click()
  })
  await page.waitForSelector('.devices__item', { timeout: 10000 })
  const deviceText = await page.$eval('.devices__item', (el) => el.textContent ?? '')
  record(
    '设备列表含「当前设备」标记',
    deviceText.includes('当前设备'),
    deviceText.trim().slice(0, 40),
  )
  await page.screenshot({ path: `${OUT}/settings-03-devices.png` })

  // ---- 数据管理：导出的 JSON 能解析 ----
  const exported = await page.evaluate(async () => {
    const response = await fetch('/api/settings/export?format=json', { credentials: 'include' })
    const text = await response.text()
    return { status: response.status, body: text }
  })
  let schema = ''
  try {
    schema = JSON.parse(exported.body).schema ?? ''
  } catch {
    // 解析失败就留空串，下面的断言会失败并打印实际响应
  }
  record(
    '导出 JSON 可解析且带 schema',
    exported.status === 200 && schema === 'my-agent.export.v1',
    schema,
  )

  const markdown = await page.evaluate(async () => {
    const response = await fetch('/api/settings/export?format=markdown', { credentials: 'include' })
    return (await response.text()).slice(0, 20)
  })
  record('导出 Markdown 以一级标题开头', markdown.startsWith('# My Agent 对话导出'), markdown)

  // ---- 注销账号 ----
  await page.evaluate(() => {
    const items = [...document.querySelectorAll('.settings__item')]
    items.find((item) => item.textContent?.includes('数据管理'))?.click()
  })
  await page.waitForSelector('.data__danger', { timeout: 5000 })
  await page.screenshot({ path: `${OUT}/settings-04-data.png` })

  const dangerInputs = await page.$$('.data__form input')
  await dangerInputs[0].type('password123')
  await dangerInputs[1].type('注销')
  await page.evaluate(() => {
    const button = [...document.querySelectorAll('.data__danger button')].find((item) =>
      item.textContent?.includes('永久删除'),
    )
    button?.click()
  })
  await page.waitForSelector('.el-message-box', { timeout: 8000 })
  await page.evaluate(() => {
    const button = [...document.querySelectorAll('.el-message-box__btns button')].find((item) =>
      item.textContent?.includes('注销'),
    )
    button?.click()
  })
  await page.waitForFunction(() => location.pathname === '/login', { timeout: 15000 })
  record('注销后回到登录页', true)

  const leftover = await page.evaluate(async (address) => {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ email: address, password: 'password123' }),
    })
    return response.status
  }, email)
  record('注销后账号无法登录', leftover === 401, `status=${leftover}`)

  // 启动时的 /auth/me 探测与「注销后登录应失败」都会故意拿到 401，
  // 这类资源加载报错不算问题，其余一律算失败。
  const unexpected = consoleErrors.filter((message) => !message.includes('401'))
  record('控制台无非预期报错', unexpected.length === 0, unexpected.join(' | ').slice(0, 200))

  await browser.close()

  const failed = results.filter((item) => !item.ok)
  console.log(`\n${results.length - failed.length}/${results.length} passed`)
  if (failed.length > 0) {
    process.exitCode = 1
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
