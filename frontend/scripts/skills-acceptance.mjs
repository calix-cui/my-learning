/**
 * 阶段 7「技能」端到端验收：真实浏览器 + 真实后端，不 mock 前端。
 *
 * 跑法：BASE=http://127.0.0.1:5173 pnpm acceptance:skills
 * 断言：内置技能只读、自建技能能增删改、挂载状态能持久化到会话。
 * 不调用模型——技能是否真的被模型"学会"由后端单测（system 消息注入）保证。
 */
import fs from 'node:fs/promises'
import puppeteer from 'puppeteer-core'

const BASE = process.env.BASE ?? 'http://127.0.0.1:5173'
const OUT = process.env.OUT ?? '.acceptance'
const CHROME =
  process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu', '--user-data-dir=/tmp/cp-skills-e2e'],
})
const page = await browser.newPage()
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })

const errors = []
page.on('console', (message) => {
  const text = message.text()
  if (message.type() === 'error' && !text.includes('401')) errors.push(text)
})
page.on('pageerror', (error) => errors.push(String(error)))

const email = `skills-e2e-${Date.now()}@example.com`
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
  .map((cookie) => cookie.split(';')[0])
  .find((cookie) => cookie.startsWith('my_agent_session='))
if (!sessionCookie) throw new Error('注册响应没有下发 my_agent_session Cookie')

const api = (path, init = {}) =>
  fetch(`${BASE}${path}`, { ...init, headers: { ...(init.headers ?? {}), cookie: sessionCookie } })

let failures = 0
const step = async (name, fn) => {
  try {
    await fn()
    console.log('PASS', name)
  } catch (error) {
    failures += 1
    console.log('FAIL', name, '-', error.message)
  }
}

const clickByText = async (selector, text) => {
  for (const handle of await page.$$(selector)) {
    const label = await handle.evaluate((el) => (el.textContent ?? '').trim())
    if (label === text) {
      await handle.click()
      return true
    }
  }
  return false
}

/** 清空输入再打字：默认值会被追加（`uvx` + `uv` → `uvxuv` 那次的教训） */
const typeInto = async (selector, text) => {
  await page.click(selector, { clickCount: 3 })
  await page.keyboard.press('Backspace')
  await page.type(selector, text)
}

const openSettings = async () => {
  if (await page.$('.settings-window')) return
  await page.click('.layout__user-trigger')
  await page.waitForSelector('.my-menu__item', { visible: true, timeout: 5000 })
  if (!(await clickByText('.my-menu__item', '系统设置')))
    throw new Error('用户菜单里没有「系统设置」')
  await page.waitForSelector('.settings-window', { visible: true, timeout: 5000 })
}

const openSkillsSection = async () => {
  await openSettings()
  if (!(await clickByText('.settings__item', '技能'))) throw new Error('设置里没有「技能」分节')
  await page.waitForSelector('.skills__list', { visible: true, timeout: 5000 })
}

const skillNames = () =>
  page.$$eval('.skills__item-name', (items) => items.map((el) => (el.textContent ?? '').trim()))

await fs.mkdir(OUT, { recursive: true })
const origin = new URL(BASE)
await page.setCookie({
  name: 'my_agent_session',
  value: sessionCookie.split('=')[1],
  domain: origin.hostname,
  path: '/',
  httpOnly: true,
})

await page.goto(`${BASE}/chat`, { waitUntil: 'networkidle2' })
await page.waitForSelector('.chat', { timeout: 10000 })

// 造一个会话：工具条上的技能胶囊只在有会话时可点
const conversation = (
  await (
    await api('/api/conversations', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ title: '技能验收' }),
    })
  ).json()
).data

await page.reload({ waitUntil: 'networkidle2' })
await page.waitForSelector('.chat__bar', { timeout: 10000 })

await step('S-01 设置「技能」节列出 3 个内置技能并标「内置」', async () => {
  await openSkillsSection()
  const names = await skillNames()
  for (const expected of ['代码审查', '会议纪要', '决策简报']) {
    if (!names.includes(expected)) throw new Error(`缺少内置技能：${expected}`)
  }
  const builtinTags = await page.$$eval(
    '.skills__tag',
    (items) => items.filter((el) => (el.textContent ?? '').trim() === '内置').length,
  )
  if (builtinTags < 3) throw new Error(`内置标签只有 ${builtinTags} 个`)
  await page.screenshot({ path: `${OUT}/skills-01-list.png` })
})

await step('S-02 内置技能没有编辑与删除入口', async () => {
  const rows = await page.$$('.skills__item')
  const first = rows[0]
  const text = await first.evaluate((el) => (el.textContent ?? '').replace(/\s+/g, ' ').trim())
  if (!text.includes('内置')) throw new Error('第一个技能不是内置技能')
  const actions = await first.$$eval('.skills__mini', (items) =>
    items.map((el) => (el.textContent ?? '').trim()),
  )
  if (actions.includes('编辑') || actions.includes('删除')) {
    throw new Error(`内置技能出现了不该有的操作：${actions.join('/')}`)
  }
})

await step('S-03 新建自定义技能', async () => {
  if (!(await clickByText('.skills__new', '新建技能'))) throw new Error('没有「新建技能」按钮')
  await page.waitForSelector('.skills__form', { visible: true, timeout: 5000 })
  await typeInto('.skills__form input[aria-label="技能标识"]', 'weekly-report')
  await typeInto('.skills__form input[aria-label="技能名称"]', '周报')
  await typeInto('.skills__form input[aria-label="技能说明"]', '把零散进展整理成周报')
  await typeInto(
    '.skills__form textarea[aria-label="技能正文"]',
    '## 步骤\n1. 按项目分组\n2. 每条写清进展与风险',
  )
  // 白名单只勾一个工具，验证 chip 是真实交互
  const chip = await page.$('.skills__chip')
  if (chip) await chip.click()
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes('/api/skills') && response.request().method() === 'POST',
    ),
    clickByText('.skills__primary', '保存'),
  ])
  await page.waitForSelector('.skills__list', { timeout: 5000 })
  const names = await skillNames()
  if (!names.includes('周报')) throw new Error(`新建后列表里没有「周报」：${names.join('、')}`)
})

await step('S-04 编辑自定义技能改名', async () => {
  const rows = await page.$$('.skills__item')
  for (const row of rows) {
    const text = await row.evaluate((el) => (el.textContent ?? '').trim())
    if (!text.startsWith('周报')) continue
    const edit = await row.$('.skills__mini:nth-of-type(2)')
    await edit?.click()
    break
  }
  await page.waitForSelector('.skills__form', { visible: true, timeout: 5000 })
  await typeInto('.skills__form input[aria-label="技能名称"]', '周报速记')
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes('/api/skills/') && response.request().method() === 'PATCH',
    ),
    clickByText('.skills__primary', '保存'),
  ])
  await page.waitForSelector('.skills__list', { timeout: 5000 })
  const names = await skillNames()
  if (!names.includes('周报速记')) throw new Error(`改名没生效：${names.join('、')}`)
})

await step('S-05 对话工具条能挂载技能，且刷新后仍在', async () => {
  // 关设置会把 ?settings=1 从地址栏摘掉；不按 Esc 直接刷新会让设置窗重新弹出来盖住工具条
  await page.keyboard.press('Escape')
  await page.waitForSelector('.settings-layer', { hidden: true, timeout: 5000 })
  if (new URL(page.url()).searchParams.has('settings')) {
    throw new Error(`关窗后地址栏还带着 settings：${page.url()}`)
  }

  // 技能列表是进页面时拉的，改完名字重新加载才能看到新菜单
  await page.reload({ waitUntil: 'networkidle2' })
  await page.waitForSelector('button.chat__skill', { timeout: 10000 })
  await page.click('button.chat__skill')
  await page.waitForSelector('.my-menu', { timeout: 5000 })
  const menuLabels = await page.$$eval('.my-menu__item', (items) =>
    items.map((el) => (el.textContent ?? '').trim()),
  )
  if (!(await clickByText('.my-menu__item', '周报速记'))) {
    throw new Error(`菜单里没有「周报速记」，只有：${menuLabels.join('、')}`)
  }
  await page.waitForFunction(
    () => (document.querySelector('.chat__skill-label')?.textContent ?? '').trim() === '周报速记',
    { timeout: 10000 },
  )
  await page.screenshot({ path: `${OUT}/skills-02-mounted.png` })

  await page.reload({ waitUntil: 'networkidle2' })
  await page.waitForSelector('button.chat__skill', { timeout: 10000 })
  const label = await page.$eval('.chat__skill-label', (el) => (el.textContent ?? '').trim())
  if (label !== '周报速记') throw new Error(`刷新后技能胶囊是「${label}」`)

  const detail = await (await api(`/api/skills?conversation_id=${conversation.id}`)).json()
  if (detail.data.mounted !== 'weekly-report') {
    throw new Error(`后端记录的挂载是 ${detail.data.mounted}`)
  }
})

await step('S-06 删除自定义技能后会话回落到不挂技能', async () => {
  await openSkillsSection()
  const rows = await page.$$('.skills__item')
  for (const row of rows) {
    const text = await row.evaluate((el) => (el.textContent ?? '').trim())
    if (!text.startsWith('周报速记')) continue
    const danger = await row.$('.skills__mini.is-danger')
    await danger?.click()
    break
  }
  await page.waitForSelector('.my-box', { visible: true, timeout: 5000 })
  await clickByText('.my-box .my-box__btn--primary', '删除')
  await page.waitForFunction(
    () =>
      ![...document.querySelectorAll('.skills__item-name')].some((el) =>
        (el.textContent ?? '').includes('周报速记'),
      ),
    { timeout: 10000 },
  )

  await page.keyboard.press('Escape')
  await page.waitForSelector('.settings-layer', { hidden: true, timeout: 5000 })
  await page.reload({ waitUntil: 'networkidle2' })
  await page.waitForSelector('button.chat__skill', { timeout: 10000 })
  const label = await page.$eval('.chat__skill-label', (el) => (el.textContent ?? '').trim())
  if (label !== '技能') throw new Error(`删掉技能后胶囊仍显示「${label}」`)
})

await step('S-07 控制台没有报错', async () => {
  if (errors.length) throw new Error(errors.join(' | '))
})

await page.screenshot({ path: `${OUT}/skills-03-final.png` })
await browser.close()

console.log(failures === 0 ? '\n技能验收全部通过' : `\n${failures} 项失败`)
process.exit(failures === 0 ? 0 : 1)
