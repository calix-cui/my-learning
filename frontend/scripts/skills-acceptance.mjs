/**
 * Skill 目录验收。需要前后端已启动，使用临时账号验证初始化、切换与只读设置。
 * SKILL_ACCEPTANCE_ROOT 可选，指向测试服务配置的共享目录，用于安装后重扫验证。
 */
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import puppeteer from 'puppeteer-core'

const BASE = process.env.BASE ?? 'http://127.0.0.1:5173'
const ROOT = process.env.SKILL_ACCEPTANCE_ROOT
const CHROME =
  process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--no-sandbox', '--disable-gpu'],
})
const page = await browser.newPage()
await page.setViewport({ width: 1440, height: 900 })
const requests = []
const messages = []
const errors = []
page.on('request', (request) => {
  if (request.url().includes('/api/skills')) requests.push(request.url())
  if (request.method() === 'POST' && request.url().includes('/messages/stream')) {
    messages.push(JSON.parse(request.postData()))
  }
})
page.on('pageerror', (error) => errors.push(error.message))

async function clickText(selector, text) {
  await page.waitForSelector(selector)
  for (const button of await page.$$(selector)) {
    if ((await button.evaluate((el) => el.textContent.trim())) === text) {
      await button.click()
      return
    }
  }
  throw new Error(`找不到按钮 ${text}`)
}
const scans = () => requests.filter((url) => url.endsWith('/catalog/rescan')).length
async function waitReady() {
  await page.waitForSelector('.chat__skill:not(:disabled)')
}
async function openSettings() {
  await page.click('.aside__user-trigger')
  await clickText('.my-menu__item', '系统设置')
  await page.waitForSelector('.settings__item')
  const scanned = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/skills/catalog/rescan') &&
      response.request().method() === 'POST',
  )
  await clickText('.settings__item', 'Skill')
  assert.equal((await scanned).status(), 200)
  await page.waitForSelector('.skills__head')
  await page.waitForFunction(() =>
    [...document.querySelectorAll('.skills__head button')].some(
      (el) => el.textContent.trim() === '重新扫描' && !el.disabled,
    ),
  )
}

let installedDirectory
let accountCookie
try {
  const registration = await fetch(`${BASE}/api/auth/register`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      email: `skill-catalog-${Date.now()}@example.com`,
      password: 'password123',
    }),
  })
  assert.equal(registration.status, 200)
  const cookie = registration.headers
    .getSetCookie()
    .find((value) => value.startsWith('my_agent_session='))
    .split(';')[0]
  accountCookie = cookie
  const api = (url, body) =>
    fetch(BASE + url, {
      method: body ? 'POST' : 'GET',
      headers: { cookie, 'content-type': 'application/json' },
      ...(body && { body: JSON.stringify(body) }),
    })
  const conversations = []
  for (const title of ['目录验收一', '目录验收二']) {
    const response = await api('/api/conversations', { title })
    conversations.push((await response.json()).data.id)
  }
  await page.setCookie({
    name: 'my_agent_session',
    value: cookie.split('=')[1],
    url: BASE,
    httpOnly: true,
  })
  await page.goto(`${BASE}/chat/${conversations[0]}`, { waitUntil: 'networkidle2' })
  await waitReady()
  assert.equal(scans(), 1)
  console.log('PASS 登录后获取一次 Skill 目录')

  await clickText('.chat__item-main', '目录验收二')
  await page.waitForFunction((id) => location.pathname.endsWith('/' + id), {}, conversations[1])
  await clickText('.chat__item-main', '目录验收一')
  await page.waitForFunction((id) => location.pathname.endsWith('/' + id), {}, conversations[0])
  assert.equal(scans(), 1)
  assert.equal(
    requests.some((url) => url.includes('conversation_id')),
    false,
  )
  console.log('PASS 切换会话不再查询 Skill')

  await page.reload({ waitUntil: 'networkidle2' })
  await waitReady()
  assert.equal(scans(), 2)
  console.log('PASS 刷新页面重新获取一次 Skill 目录')

  await openSettings()
  assert.equal(scans(), 3)
  assert.equal(
    await page.$$eval('.skills form, .skills input, .skills textarea', (els) => els.length),
    0,
  )
  const settingsText = await page.$eval('.skills', (el) => el.textContent)
  assert.equal(settingsText.includes('编辑'), false)
  assert.equal(settingsText.includes('新建'), false)
  await clickText('.skills__action', '查看说明')
  await page.waitForSelector('.skills .markdown-content')
  console.log('PASS 设置只读，说明按需加载')
  if (process.env.OUT) {
    await fs.mkdir(process.env.OUT, { recursive: true })
    for (const mode of ['light', 'dark']) {
      await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: mode }])
      await page.waitForFunction(
        (value) => document.documentElement.dataset.mode === value,
        {},
        mode,
      )
      await page.screenshot({ path: path.join(process.env.OUT, `skill-catalog-${mode}.png`) })
    }
    await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }])
  }

  if (ROOT) {
    installedDirectory = path.join(ROOT, `acceptance-extra-${Date.now()}`)
    await fs.mkdir(installedDirectory, { recursive: true })
    await fs.writeFile(
      path.join(installedDirectory, 'SKILL.md'),
      [
        '---',
        'name: 浏览器新安装流程',
        'description: 用于验证安装与重新扫描',
        '---',
        '',
        '按要求整理用户输入。',
      ].join('\n'),
    )
  }
  const rescanned = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/skills/catalog/rescan') &&
      response.request().method() === 'POST',
  )
  await clickText('.skills__action', '重新扫描')
  assert.equal((await rescanned).status(), 200)
  if (ROOT) {
    await page.waitForFunction(() =>
      document.querySelector('.skills')?.textContent.includes('浏览器新安装流程'),
    )
  }
  await page.waitForFunction(() =>
    [...document.querySelectorAll('.skills__head button')].some(
      (el) => el.textContent.trim() === '重新扫描' && !el.disabled,
    ),
  )
  assert.equal(scans(), 4)
  if (ROOT)
    assert.ok((await page.$eval('.skills', (el) => el.textContent)).includes('浏览器新安装流程'))
  console.log('PASS 设置重新扫描后更新目录')

  await page.keyboard.press('Escape')
  await page.waitForFunction(() => !document.querySelector('.settings'))
  await page.click('.chat__new')
  await waitReady()
  await page.click('.chat__skill')
  const choices = await page.$$eval('.my-menu__item', (els) =>
    els.map((el) => el.textContent.trim()),
  )
  const choice = choices.find((label) => label.includes('builtin:meeting-notes'))
  assert.ok(choice)
  await clickText('.my-menu__item', choice)
  await page.waitForFunction(() =>
    document.querySelector('.chat__skill-label')?.textContent.includes('会议纪要'),
  )
  assert.equal(scans(), 4)
  console.log('PASS 空白草稿可为本条消息选择 Skill')

  if (process.env.SKILL_ACCEPTANCE_SEND === '1') {
    await page.type('.chat__composer textarea', '整理这条记录，按本次 Skill 输出')
    await page.click('.composer__send')
    await page.waitForSelector('.chat__row--assistant + .timeline', { timeout: 45000 })
    await page.waitForFunction(
      () =>
        !document.querySelector('.composer__send.is-loading') &&
        document.querySelector('.chat__skill-label')?.textContent === 'Skill',
    )
    await page.click('.timeline > summary')
    await page.waitForFunction(() =>
      document.querySelector('.timeline')?.textContent.includes('会议纪要'),
    )
    assert.equal(scans(), 4)
    assert.deepEqual(messages[0].skill_keys, ['builtin:meeting-notes'])
    console.log('PASS 发送后清除本条选择，回复保留 Skill 加载记录')

    if (ROOT && process.env.SKILL_ACCEPTANCE_AUTO === '1') {
      await page.type(
        '.chat__composer textarea',
        '请使用目录中的「浏览器新安装流程」Skill，把这段信息整理成一句话：今天完成了本地目录和只读设置。',
      )
      await page.click('.composer__send')
      await page.waitForFunction(
        () =>
          document.querySelectorAll('.chat__row--assistant').length === 2 &&
          !document.querySelector('.composer__send.is-loading'),
        { timeout: 60000 },
      )
      const timelines = await page.$$('.chat__row--assistant + .timeline')
      assert.equal(timelines.length, 2)
      await (await timelines[1].$('summary')).click()
      await page.waitForFunction(
        (element) => element.textContent.includes('浏览器新安装流程'),
        { timeout: 15000 },
        timelines[1],
      )
      assert.deepEqual(messages[1].skill_keys, [])
      assert.equal(scans(), 4)
      console.log('PASS 模型根据任务按需加载本地 Skill，发送期间没有目录查询')
    }
  }
  assert.deepEqual(errors, [])
  console.log('Skill 浏览器验收全部通过')
} finally {
  if (accountCookie) {
    const response = await fetch(BASE + '/api/auth/me', {
      method: 'DELETE',
      headers: { cookie: accountCookie, 'content-type': 'application/json' },
      body: JSON.stringify({ password: 'password123' }),
    })
    if (!response.ok) console.error('临时账号清理失败', response.status)
  }
  if (installedDirectory) await fs.rm(installedDirectory, { recursive: true, force: true })
  await browser.close()
}
