// 商品管理后台 · 端到端验收脚本
//
// 用法：
//   1. 先起后端（backend）与前端（pnpm dev，默认 5173）
//   2. pnpm acceptance               # 默认打 http://127.0.0.1:5173
//      BASE=http://127.0.0.1:4173 pnpm acceptance   # 也可以打 preview
//
// 依赖：puppeteer-core（devDependency）+ 本机已安装的 Chrome/Chromium。
// 覆盖 18 项 UI 用例：列表/分页/统计卡/新增（含价格精度校验）/搜索/编辑/
// 删除（取消 + 确认）/空态/分类新增&重名&改名&删除/概览。
// 截图与结果落在 <repo>/.acceptance/ 下（已在 .gitignore 中忽略）。
//
// 前置数据：库里最好有 ≥2 页商品（本仓库 seed 后 14 条），脚本会自己创建并清理 E2E 数据。
import puppeteer from 'puppeteer-core'
import fs from 'node:fs'
import path from 'node:path'

const CHROME =
  process.env.CHROME_PATH ||
  (process.platform === 'darwin'
    ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    : process.platform === 'win32'
      ? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
      : '/usr/bin/google-chrome')
const BASE = process.env.BASE || 'http://127.0.0.1:5173'
const OUT = process.env.OUT || path.join(process.cwd(), '.acceptance')
fs.mkdirSync(OUT, { recursive: true })

const results = []
const pass = (id, detail) => {
  results.push({ id, ok: true, detail })
  console.log(`PASS ${id} ${detail}`)
}
const fail = (id, detail) => {
  results.push({ id, ok: false, detail })
  console.log(`FAIL ${id} ${detail}`)
}

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars'],
  defaultViewport: { width: 1440, height: 900, deviceScaleFactor: 2 },
})
const page = await browser.newPage()
page.on('pageerror', (e) => console.log('PAGE EXCEPTION:', e.message))

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const shot = async (name) => {
  await sleep(400)
  await page.screenshot({ path: `${OUT}/${name}.png` })
}
const bodyText = () => page.evaluate(() => document.body.innerText)
const rows = () =>
  page.evaluate(() =>
    [...document.querySelectorAll('.el-table__body .el-table__row')].map((r) =>
      r.innerText.replace(/\s+/g, ' ').trim(),
    ),
  )
const toast = () =>
  page.evaluate(() => {
    const el = document.querySelector('.el-message__content')
    return el ? el.textContent.trim() : ''
  })
const clickText = async (text, scope = 'button') => {
  const ok = await page.evaluate(
    (t, s) => {
      const nodes = [...document.querySelectorAll(s)]
      const hit = nodes.find((n) => n.textContent.replace(/\s+/g, '') === t.replace(/\s+/g, ''))
      if (!hit) return false
      hit.click()
      return true
    },
    text,
    scope,
  )
  await sleep(500)
  return ok
}
// 真实鼠标点击下拉项，避免 Element Plus 合成事件失效
const pickSelect = async (selectSel, optionText) => {
  await page.click(selectSel)
  await sleep(600)
  const box = await page.evaluate((t) => {
    const items = [...document.querySelectorAll('.el-select-dropdown__item')].filter(
      (i) => i.offsetParent !== null,
    )
    const hit = items.find((i) => i.innerText.trim() === t)
    if (!hit) return null
    const r = hit.getBoundingClientRect()
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
  }, optionText)
  if (!box) return false
  await page.mouse.click(box.x, box.y)
  await sleep(400)
  return true
}
const cleanRow = async (name) => {
  // 清理：删除测试商品/分类，保持数据库干净
  await page.goto(`${BASE}/products`, { waitUntil: 'networkidle2' })
  await sleep(800)
  const input = 'input[placeholder="搜索商品名称，回车查询"]'
  await page.click(input)
  await page.type(input, name)
  await page.keyboard.press('Enter')
  await sleep(1500)
  let list = await rows()
  for (const _ of list.filter((t) => t.includes(name))) {
    await page.evaluate((n) => {
      const row = [...document.querySelectorAll('.el-table__body .el-table__row')].find((x) =>
        x.innerText.includes(n),
      )
      row.querySelectorAll('button')[1].click()
    }, name)
    await sleep(700)
    await clickText('删除', '.el-message-box button')
    await sleep(1200)
  }
}

await page.goto(`${BASE}/products`, { waitUntil: 'networkidle2' })
await page.waitForSelector('.el-table__body .el-table__row', { timeout: 15000 })
await sleep(800)

// 1. 列表页
{
  const info = await page.evaluate(() => {
    const trs = [...document.querySelectorAll('.el-table__body .el-table__row')]
    const headers = [...document.querySelectorAll('.el-table__header th')].map((th) =>
      th.innerText.trim(),
    )
    return {
      rowCount: trs.length,
      headers,
      stats: [...document.querySelectorAll('.stat-card')].map((c) =>
        c.innerText.replace(/\n/g, ' ').trim(),
      ),
      pagerTotal: (document.body.innerText.match(/共\s*\d+\s*条/) || [''])[0],
      pageButtons: [...document.querySelectorAll('.el-pager li')].length,
    }
  })
  const need = ['ID', '商品名称', '分类', '价格', '库存', '状态', '创建时间', '操作']
  const missing = need.filter((h) => !info.headers.includes(h))
  if (info.rowCount > 0 && missing.length === 0)
    pass('UI-01 列表渲染', `${info.rowCount} 行；表头完整`)
  else fail('UI-01 列表渲染', `行数=${info.rowCount} 缺=${missing.join(',')}`)
  if (info.pagerTotal && info.pageButtons >= 2)
    pass('UI-02 分页条', `${info.pagerTotal}；页码按钮 ${info.pageButtons} 个`)
  else fail('UI-02 分页条', `${info.pagerTotal} 按钮=${info.pageButtons}`)
  if (info.stats.length === 3) pass('UI-03 统计卡', info.stats.join(' | '))
  else fail('UI-03 统计卡', JSON.stringify(info.stats))
  await shot('01-product-list')
}

// 2. 新增商品：价格精度校验 + 正常提交
{
  await clickText('新增商品')
  await page.waitForSelector('.el-dialog input[placeholder="请输入商品名称"]', { timeout: 8000 })
  pass('UI-04 打开新增弹窗', 'dialog visible')

  await page.type('.el-dialog input[placeholder="请输入商品名称"]', 'E2E测试商品')
  const picked = await pickSelect('.el-dialog .el-select__wrapper', '饮料')
  if (picked) pass('UI-05 分类下拉', '选中「饮料」')
  else fail('UI-05 分类下拉', '下拉项未找到')

  await page.click('.el-dialog input[placeholder="请输入价格，如 3.50"]')
  await page.type('.el-dialog input[placeholder="请输入价格，如 3.50"]', '12.345')
  await page.click('.el-dialog .el-dialog__header')
  await sleep(600)
  const errs = await page.evaluate(() =>
    [...document.querySelectorAll('.el-dialog .el-form-item__error')].map((e) =>
      e.innerText.trim(),
    ),
  )
  if (errs.some((t) => t.includes('2 位小数'))) pass('UI-06 价格精度校验', errs.join('; '))
  else fail('UI-06 价格精度校验', JSON.stringify(errs))
  await shot('02-form-validation')

  const priceSel = '.el-dialog input[placeholder="请输入价格，如 3.50"]'
  await page.click(priceSel, { clickCount: 3 })
  await page.keyboard.press('Backspace')
  await page.type(priceSel, '12.34')
  const stockSel = '.el-dialog .el-input-number input'
  await page.click(stockSel, { clickCount: 3 })
  await page.keyboard.press('Backspace')
  await page.type(stockSel, '7')
  await clickText('确定')
  await sleep(1800)
  const msg = await toast()
  const list = await rows()
  const hit = list.find((r) => r.includes('E2E测试商品'))
  if (msg.includes('新增成功') && hit && hit.includes('12.34') && hit.includes('饮料'))
    pass('UI-07 新增提交并回显', hit)
  else fail('UI-07 新增提交并回显', `toast="${msg}" row=${hit}`)
  await shot('03-list-after-create')
}

// 3. 搜索
{
  const sel = 'input[placeholder="搜索商品名称，回车查询"]'
  await page.click(sel)
  await page.type(sel, 'E2E测试商品')
  await page.keyboard.press('Enter')
  await sleep(1800)
  const list = await rows()
  const hit = list.filter((r) => r.includes('E2E测试商品'))
  if (hit.length === 1) pass('UI-08 关键词搜索', hit[0])
  else fail('UI-08 关键词搜索', `rows=${list.length} ${JSON.stringify(list.slice(0, 3))}`)
  await shot('04-search-result')
}

// 4. 编辑：库存改 9
{
  const clicked = await page.evaluate(() => {
    const row = [...document.querySelectorAll('.el-table__body .el-table__row')].find((r) =>
      r.innerText.includes('E2E测试商品'),
    )
    if (!row) return false
    const btn = [...row.querySelectorAll('button')].find((b) => b.innerText.trim() === '编辑')
    if (!btn) return false
    btn.click()
    return true
  })
  await sleep(1500)
  const stockSel = '.el-dialog .el-input-number input'
  if (clicked && (await page.$(stockSel))) {
    await page.click(stockSel, { clickCount: 3 })
    await page.keyboard.press('Backspace')
    await page.type(stockSel, '9')
    await clickText('保存')
    await sleep(1800)
    const msg = await toast()
    const list = await rows()
    const hit = list.find((r) => r.includes('E2E测试商品'))
    if (msg.includes('修改成功') && hit && /\s9\s/.test(hit)) pass('UI-09 编辑保存', hit)
    else fail('UI-09 编辑保存', `toast="${msg}" row=${hit}`)
    await shot('05-after-edit')
  } else {
    fail('UI-09 编辑保存', '编辑按钮或弹窗未就绪')
  }
}

// 5. 删除：先取消再确认
{
  const clicked = await page.evaluate(() => {
    const row = [...document.querySelectorAll('.el-table__body .el-table__row')].find((r) =>
      r.innerText.includes('E2E测试商品'),
    )
    if (!row) return false
    const btn = [...row.querySelectorAll('button')].find((b) => b.innerText.trim() === '删除')
    if (!btn) return false
    btn.click()
    return true
  })
  await sleep(900)
  const boxText = await page.evaluate(() => {
    const box = document.querySelector('.el-message-box')
    return box ? box.innerText.replace(/\n/g, ' ') : ''
  })
  await shot('06-delete-confirm')
  if (clicked && boxText.includes('删除')) pass('UI-10 删除二次确认', boxText.slice(0, 60))
  else fail('UI-10 删除二次确认', boxText)

  await clickText('取消', '.el-message-box button')
  await sleep(800)
  const stillThere = (await rows()).some((r) => r.includes('E2E测试商品'))
  if (stillThere) pass('UI-11 取消删除不生效', '行仍在')

  await page.evaluate(() => {
    const row = [...document.querySelectorAll('.el-table__body .el-table__row')].find((r) =>
      r.innerText.includes('E2E测试商品'),
    )
    ;[...row.querySelectorAll('button')].find((b) => b.innerText.trim() === '删除').click()
  })
  await sleep(800)
  await clickText('删除', '.el-message-box button')
  await sleep(1800)
  const msg = await toast()
  const gone = !(await rows()).some((r) => r.includes('E2E测试商品'))
  if (msg.includes('删除成功') && gone) pass('UI-12 删除生效', msg)
  else fail('UI-12 删除生效', `toast="${msg}" gone=${gone}`)
}

// 6. 空态
{
  const sel = 'input[placeholder="搜索商品名称，回车查询"]'
  await page.click(sel, { clickCount: 3 })
  await page.keyboard.press('Backspace')
  await page.type(sel, '不存在的商品XYZ')
  await page.keyboard.press('Enter')
  await sleep(1500)
  const text = await bodyText()
  if (text.includes('没有符合条件的商品') && text.includes('清空筛选'))
    pass('UI-13 搜索空态', '空态文案 + 清空筛选')
  else fail('UI-13 搜索空态', text.slice(0, 120))
  await shot('07-empty-state')
}

// 7. 分类管理
{
  await page.goto(`${BASE}/categories`, { waitUntil: 'networkidle2' })
  await page.waitForSelector('.el-table__body .el-table__row', { timeout: 15000 })
  await sleep(800)
  await shot('08-category-manage')

  await clickText('新增分类')
  await page.waitForSelector('.el-dialog input[placeholder="请输入分类名称"]', { timeout: 8000 })
  await page.type('.el-dialog input[placeholder="请输入分类名称"]', 'E2E测试分类')
  await clickText('确定')
  await sleep(1800)
  let msg = await toast()
  let text = await bodyText()
  if (msg.includes('新增成功') && text.includes('E2E测试分类')) pass('UI-14 新增分类', msg)
  else fail('UI-14 新增分类', `toast="${msg}"`)

  await clickText('新增分类')
  await page.waitForSelector('.el-dialog input[placeholder="请输入分类名称"]', { timeout: 8000 })
  await page.type('.el-dialog input[placeholder="请输入分类名称"]', 'E2E测试分类')
  await clickText('确定')
  await sleep(1800)
  msg = await toast()
  if (msg.includes('已存在')) pass('UI-15 分类重名拦截', msg)
  else fail('UI-15 分类重名拦截', `toast="${msg}"`)
  await shot('09-category-duplicate')
  await clickText('取消')
  await sleep(600)

  const renamed = await page.evaluate(() => {
    const row = [...document.querySelectorAll('.el-table__body .el-table__row')].find(
      (r) => r.querySelectorAll('td')[1]?.innerText.trim() === 'E2E测试分类',
    )
    if (!row) return false
    ;[...row.querySelectorAll('button')].find((b) => b.innerText.trim() === '改名').click()
    return true
  })
  await sleep(1200)
  if (renamed) {
    await page.click('.el-dialog input[placeholder="请输入分类名称"]', { clickCount: 3 })
    await page.keyboard.press('Backspace')
    await page.type('.el-dialog input[placeholder="请输入分类名称"]', 'E2E测试分类2')
    await clickText('确定')
    await sleep(1800)
    msg = await toast()
    if ((await bodyText()).includes('E2E测试分类2')) pass('UI-16 分类改名', msg)
    else fail('UI-16 分类改名', `toast="${msg}"`)
  } else {
    fail('UI-16 分类改名', '改名按钮未找到')
  }

  const deleted = await page.evaluate(() => {
    const row = [...document.querySelectorAll('.el-table__body .el-table__row')].find(
      (r) => r.querySelectorAll('td')[1]?.innerText.trim() === 'E2E测试分类2',
    )
    if (!row) return false
    ;[...row.querySelectorAll('button')].find((b) => b.innerText.trim() === '删除').click()
    return true
  })
  await sleep(900)
  await clickText('删除', '.el-message-box button')
  await sleep(1800)
  msg = await toast()
  const gone = !(await bodyText()).includes('E2E测试分类2')
  if (deleted && msg.includes('删除成功') && gone) pass('UI-17 删除空分类', msg)
  else fail('UI-17 删除空分类', `toast="${msg}" gone=${gone}`)
}

// 8. 概览
{
  await page.goto(`${BASE}/dashboard`, { waitUntil: 'networkidle2' })
  await sleep(1800)
  const text = await bodyText()
  if (text.includes('商品总数') && text.includes('各分类商品数') && text.includes('最近新增商品'))
    pass('UI-18 概览页', text.replace(/\s+/g, ' ').slice(0, 80))
  else fail('UI-18 概览页', text.slice(0, 120))
  await shot('10-dashboard')
}

// 9. 清理历史残留（上次失败跑留下的 E2E 数据）
await cleanRow('E2E测试商品')

await browser.close()
const failed = results.filter((r) => !r.ok)
fs.writeFileSync(`${OUT}/result.json`, JSON.stringify(results, null, 2))
console.log(`\n==== 汇总：${results.length - failed.length}/${results.length} 通过 ====`)
if (failed.length) {
  failed.forEach((f) => console.log(' - FAIL', f.id, f.detail))
  process.exit(1)
}
