/**
 * 阶段 6「工具生态与权限治理」端到端验收：真实浏览器 + 真实模型，不 mock 前端。
 *
 * 跑法：BASE=http://127.0.0.1:5173 pnpm acceptance:tools
 * 断言两件事：写工具执行前一定会停下等用户点；批/拒之后这次运行能接着跑完。
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
  args: ['--no-sandbox', '--disable-gpu', '--user-data-dir=/tmp/cp-tools-e2e'],
})
const page = await browser.newPage()
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })

const gotoPage = async (url) => {
  await page.goto(url, { waitUntil: 'networkidle2' })
  await page
    .evaluate(() => document.getElementById('__vue-devtools-container__')?.remove())
    .catch(() => undefined)
}

const errors = []
page.on('console', (message) => {
  const text = message.text()
  if (message.type() === 'error' && !text.includes('401')) errors.push(text)
})
page.on('pageerror', (error) => errors.push(String(error)))

const email = `tools-e2e-${Date.now()}@example.com`
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

/** 等一次运行彻底停下：流式气泡消失，且没有正在转的按钮 */
const waitIdle = async (timeout = 120000) => {
  await page.waitForFunction(() => !document.querySelector('.chat__bubble--streaming'), { timeout })
  await page.waitForFunction(
    () => !document.querySelector('.chat__composer .el-button.is-loading'),
    { timeout },
  )
}

const openSettings = async () => {
  if (await page.$('.settings')) return
  await page.click('.aside__user-trigger')
  await page.waitForSelector('.my-menu__item', { visible: true, timeout: 5000 })
  const clicked = await page.$$eval('.my-menu__item', (items) => {
    const target = items.find((item) => (item.textContent ?? '').includes('系统设置'))
    if (!target) return false
    target.click()
    return true
  })
  if (!clicked) throw new Error('用户菜单里没有「系统设置」')
  await page.waitForSelector('.settings', { visible: true, timeout: 5000 })
}

/**
 * 真实鼠标点击元素（按坐标点），而不是 evaluate 里的 el.click()。
 * 设置窗口曾被一层遮罩盖住：坐标点击能暴露这个问题，DOM click 不能。
 */
const clickByText = async (selector, text) => {
  const handles = await page.$$(selector)
  for (const handle of handles) {
    const label = await handle.evaluate((el) => (el.textContent ?? '').trim())
    if (label === text) {
      await handle.click()
      return true
    }
  }
  return false
}

const openToolsSection = async () => {
  await openSettings()
  if (!(await clickByText('.settings__item', '工具'))) throw new Error('设置里没有「工具」分节')
  await page.waitForSelector('.tools__row', { visible: true, timeout: 5000 })
}

/** 发一条会触发写工具的消息，并等到审批卡片出现（或超时） */
const sendRenamePrompt = async (title) => {
  if (!(await page.$('.chat__composer textarea'))) {
    await page.click('.chat__new')
    await page.waitForSelector('.chat__composer textarea', { timeout: 5000 })
  }
  await page.click('.chat__composer textarea')
  await page.type(
    '.chat__composer textarea',
    `请调用工具把当前会话的标题改成「${title}」，改完用一句话告诉我。`,
  )
  await page.click('.chat__composer .el-button--primary')
  await page.waitForSelector('.approval', { visible: true, timeout: 120000 })
}

await fs.mkdir(OUT, { recursive: true })
const origin = new URL(BASE)
await page.setCookie({
  name: 'my_agent_session',
  value: sessionCookie.split('=')[1],
  domain: origin.hostname,
  path: '/',
  httpOnly: true,
})

await gotoPage(`${BASE}/chat`)
await page.waitForSelector('.chat', { timeout: 10000 })
const before = await (await api('/api/conversations?page=1&page_size=100')).json()
for (const item of before.data.items) {
  await api(`/api/conversations/${item.id}`, { method: 'DELETE' })
}
await page.reload({ waitUntil: 'networkidle2' })
await page.waitForSelector('.chat__empty-title', { timeout: 10000 })

await step('T-01 设置里有「工具」分节，写工具标了「需确认」', async () => {
  await openToolsSection()
  const rows = await page.$$eval('.tools__row', (items) =>
    items.map((item) => (item.textContent ?? '').replace(/\s+/g, ' ').trim()),
  )
  if (!rows.some((row) => row.includes('rename_conversation'))) {
    throw new Error(`工具清单=${JSON.stringify(rows)}`)
  }
  if (!rows.some((row) => row.includes('rename_conversation') && row.includes('需确认'))) {
    throw new Error('写工具没有标「需确认」')
  }
  await page.screenshot({ path: `${OUT}/tools-01-settings.png` })
})

await step('T-02 设置窗口内部能点、点遮罩能关、关掉后页面恢复可点', async () => {
  // 换一节再换回来：真的坐标点击面板里的按钮
  if (!(await clickByText('.settings__item', '外观'))) throw new Error('没有「外观」分节')
  await page.waitForSelector('.appearance', { visible: true, timeout: 5000 })
  if (!(await clickByText('.settings__item', '工具'))) throw new Error('没有「工具」分节')
  await page.waitForSelector('.tools__row', { visible: true, timeout: 5000 })

  // 点左边缘的遮罩关闭窗口，然后页面上随便点一个按钮
  await page.mouse.click(8, 450)
  await page.waitForFunction(() => !document.querySelector('.settings'), { timeout: 5000 })
  await page.click('.chat__new')
  await page.waitForSelector('.chat__composer textarea', { visible: true, timeout: 5000 })

  // 后续用例还要用设置
  await openToolsSection()
})

await step('T-03 关掉一个工具后保存并回显', async () => {
  const name = 'calculator'
  const index = await page.$$eval(
    '.tools__row',
    (items, target) => {
      return items.findIndex((item) => (item.textContent ?? '').includes(target))
    },
    name,
  )
  if (index < 0) throw new Error('清单里没有 calculator')
  await page.$$eval(
    '.tools__row',
    (items, target) => {
      const row = items.find((item) => (item.textContent ?? '').includes(target))
      row?.querySelector('.el-switch')?.click()
    },
    name,
  )
  await page.waitForFunction(
    (target) => {
      const row = [...document.querySelectorAll('.tools__row')].find((item) =>
        (item.textContent ?? '').includes(target),
      )
      return row?.querySelector('.el-switch')?.classList.contains('is-checked') === false
    },
    { timeout: 10000 },
    name,
  )
  // 界面是乐观更新，PUT 还在路上时后端仍是 true，所以要轮询
  for (let i = 0; i < 20; i += 1) {
    const data = await (await api('/api/settings/tools')).json()
    const calculator = data.data.items.find((item) => item.name === name)
    if (calculator?.enabled === false) break
    if (i === 19) throw new Error('后端没有记下禁用状态')
    await new Promise((resolve) => setTimeout(resolve, 200))
  }

  // 复原，后面的用例还要用工具
  await page.$$eval(
    '.tools__row',
    (items, target) => {
      const row = items.find((item) => (item.textContent ?? '').includes(target))
      row?.querySelector('.el-switch')?.click()
    },
    name,
  )
  await page.waitForFunction(
    (target) => {
      const row = [...document.querySelectorAll('.tools__row')].find((item) =>
        (item.textContent ?? '').includes(target),
      )
      return row?.querySelector('.el-switch')?.classList.contains('is-checked') === true
    },
    { timeout: 10000 },
    name,
  )
  // 复原也是一次 PUT：等它在后端落地，否则下一次读到的还是旧状态
  for (let i = 0; i < 20; i += 1) {
    const data = await (await api('/api/settings/tools')).json()
    const item = data.data.items.find((entry) => entry.name === name)
    if (item?.enabled === true) break
    if (i === 19) throw new Error('复原没有生效')
    await new Promise((resolve) => setTimeout(resolve, 200))
  }
})

await step('T-04 改每日上限并回显', async () => {
  if (!(await page.$('.tools__budget-form input'))) throw new Error('没有每日上限输入框')
  // el-input-number 的内部 input 对真实键盘输入有节流，这里用原生 setter 触发它的 input 事件
  const typed = await page.$eval('.tools__budget-form input', (el) => {
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
    setter.call(el, '300')
    el.dispatchEvent(new Event('input', { bubbles: true }))
    el.dispatchEvent(new Event('change', { bubbles: true }))
    return el.value
  })
  if (typed !== '300') throw new Error(`输入框没有变成 300：${typed}`)
  await page.$eval('.tools__save', (el) => el.click())
  for (let i = 0; i < 20; i += 1) {
    const data = await (await api('/api/settings/tools')).json()
    if (data.data.daily_tool_budget === 300) break
    if (i === 19) throw new Error(`后端上限没有更新：${data.data.daily_tool_budget}`)
    await new Promise((resolve) => setTimeout(resolve, 200))
  }
  const shown = await page.$eval('.tools__budget-head .tools__meta', (el) =>
    (el.textContent ?? '').trim(),
  )
  if (!shown.includes('/ 300')) throw new Error(`界面显示=${shown}`)
})

await step('T-05 写工具执行前停下等确认', async () => {
  await page.keyboard.press('Escape')
  await page.waitForFunction(() => !document.querySelector('.settings'), { timeout: 5000 })
  await page.click('.chat__new')
  await page.waitForSelector('.chat__composer textarea', { timeout: 5000 })
  if ((await page.$eval('.chat__mode', (el) => el.getAttribute('aria-pressed'))) !== 'true') {
    await page.click('.chat__mode')
  }
  await sendRenamePrompt('周报')
  // 卡片先于流关闭出现，按钮会短暂是「执行中…」，等它可点再断言
  await page.waitForFunction(
    () =>
      document.querySelector('.approval__btn--primary')?.textContent?.includes('批准执行') === true,
    { timeout: 15000 },
  )
  const card = await page.$eval('.approval', (el) => (el.textContent ?? '').replace(/\s+/g, ' '))
  if (!card.includes('rename_conversation')) throw new Error(`卡片内容=${card.slice(0, 80)}`)
  if (!card.includes('批准执行')) throw new Error('卡片没有批准按钮')
  await page.screenshot({ path: `${OUT}/tools-02-approval.png` })
})

await step('T-06 拒绝后运行继续跑完，且工具没有执行', async () => {
  const titleBefore = await page.$eval('.chat__title', (el) => (el.textContent ?? '').trim())
  await page.type('.approval__note', '标题我自己改')
  await page.click('.approval__btn--ghost')
  await waitIdle()
  if (await page.$('.approval')) throw new Error('拒绝后卡片还在')
  await page.waitForFunction(
    () => document.querySelectorAll('.timeline__item--tool_result').length >= 1,
    { timeout: 60000 },
  )
  const result = await page.$eval('.timeline__item--tool_result .timeline__text', (el) =>
    (el.textContent ?? '').trim(),
  )
  if (!result.includes('拒绝')) throw new Error(`工具结果=${result}`)
  const titleAfter = await page.$eval('.chat__title', (el) => (el.textContent ?? '').trim())
  if (titleAfter === '周报') throw new Error('拒绝了却还是改了标题')
  console.log('   拒绝前标题:', titleBefore, '拒绝后标题:', titleAfter)
})

await step('T-07 批准后工具真的执行，标题变了', async () => {
  const stamp = `周报${Date.now() % 10000}`
  await sendRenamePrompt(stamp)
  await page.click('.approval__btn--primary')
  await waitIdle()
  if (await page.$('.approval')) throw new Error('批准后卡片还在')
  await page.waitForFunction(
    (expected) => document.querySelector('.chat__title')?.textContent?.includes(expected) === true,
    { timeout: 60000 },
    stamp,
  )
  await page.screenshot({ path: `${OUT}/tools-03-approved.png` })
})

await step('T-08 刷新后没有残留的审批卡片', async () => {
  await page.reload({ waitUntil: 'networkidle2' })
  await page.waitForSelector('.chat', { timeout: 15000 })
  await page.waitForFunction(() => !document.querySelector('.chat__bubble--streaming'), {
    timeout: 30000,
  })
  if (await page.$('.approval')) throw new Error('刷新后又冒出一张待审批卡片')
})

await step('T-09 控制台无非预期报错', async () => {
  if (errors.length) throw new Error(errors.slice(0, 2).join(' | '))
})

await browser.close()
console.log(failures ? `\n${failures} 项失败` : '\n全部通过')
process.exit(failures ? 1 : 0)
