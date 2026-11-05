# 验收记录（v1.0）

| 项 | 内容 |
| --- | --- |
| 验收人 | Tech Lead |
| 日期 | 2026-11-06 |
| 环境 | macOS · Node v24.21.0 · pnpm 12.10.1 · Python 3.15 · MySQL 8（127.0.0.1:3306/fastapi_demo） |
| 被测版本 | 前端 `fullstack/product-admin`（commit 前工作区）+ 后端 `python/fastapi-demo` |
| 数据基线 | 3 个分类（饮料/零食/乳品）、14 件商品（12 件 seed + 历史数据），其中 2 件下架 |
| 结论 | **通过**：P0 16 条全部可用；UI 自动化 18/18；后端 `make check` 绿（ruff + 23 passed） |

## 1. 执行方式

| 层 | 命令 | 说明 |
| --- | --- | --- |
| 后端 | `cd python/fastapi-demo && make check` | ruff check + ruff format --check + pytest |
| 接口 | `curl http://127.0.0.1:8000/api/...` | 真实 MySQL，逐条核对响应体 |
| UI | `cd fullstack/product-admin && pnpm acceptance` | puppeteer-core + 本机 Chrome，1440×900 @2x，真实点击/输入 |
| 视觉 | `docs/product-admin/images/*.png` | 与 `docs/design/images/*.png` 逐项比对 |

`pnpm acceptance` 的产物（10 张过程截图 + `result.json`）落在 `.acceptance/`，已被 `.gitignore` 忽略；脚本末尾自动清理它创建的商品与分类。

## 2. UI 用例（自动化，18 项）

| 用例 | 步骤 | 期望 | 实际 | 结论 |
| --- | --- | --- | --- | --- |
| UI-01 | 打开 `/products` | 表格有数据，8 列表头齐全 | 10 行；ID/名称/分类/价格/库存/状态/创建时间/操作齐全 | ✅ |
| UI-02 | 看分页条 | 显示总数与多页 | 共 14 条；页码 1、2 | ✅ |
| UI-03 | 看统计卡 | 三张卡：总数/分类数/筛选结果 | 14 / 3 / 14（hint 为「未使用筛选条件」） | ✅ |
| UI-04 | 点「新增商品」 | 弹窗出现 | 弹窗可见，标题「新增商品」 | ✅ |
| UI-05 | 分类下拉选「饮料」 | 选中并回填 | 显示「饮料」 | ✅ |
| UI-06 | 价格输入 `12.345` 后提交 | 拦截并提示 2 位小数 | 红框 + 「价格最多 2 位小数，且不能小于 0」，未提交 | ✅ |
| UI-07 | 价格改 `12.34`、库存 `7`，提交 | toast 成功，首行出现且分类正确 | 「商品新增成功」，行含 ¥12.34 / 7 / 饮料 | ✅ |
| UI-08 | 关键词搜「E2E测试商品」回车 | 命中 1 条 | 命中 1 条，URL 带 `keyword` | ✅ |
| UI-09 | 编辑该行，库存改 `9`，保存 | toast 成功，行内库存变 9 | 「商品修改成功」，库存 9 | ✅ |
| UI-10 | 点「删除」 | 二次确认弹层，含不可恢复提示 | 「确定要删除商品「E2E测试商品」吗？删除后不可恢复。」 | ✅ |
| UI-11 | 确认框点「取消」 | 行仍在 | 行仍在 | ✅ |
| UI-12 | 再次删除并点「删除」 | toast 成功，行消失 | 「删除成功」，行消失 | ✅ |
| UI-13 | 搜「不存在的商品XYZ」 | 空态文案 + 清空筛选 | 「没有符合条件的商品」+ 副文案 + 「清空筛选」 | ✅ |
| UI-14 | 分类页新增「E2E测试分类」 | toast 成功，列表出现 | 「分类新增成功」 | ✅ |
| UI-15 | 再建同名分类 | 后端 409，前端原样提示 | 「分类名称已存在」 | ✅ |
| UI-16 | 改名「E2E测试分类2」 | toast 成功，名称更新 | 「分类名称已更新」 | ✅ |
| UI-17 | 删除该空分类 | toast 成功，行消失 | 「删除成功」 | ✅ |
| UI-18 | 打开 `/dashboard` | 统计卡 + 分类分布 + 最近新增 | 三块内容齐全，数据与列表一致 | ✅ |

## 3. 接口契约（curl 抽查）

| 场景 | 期望 | 实际 |
| --- | --- | --- |
| `GET /api/products?page=1&page_size=2` | 200，`data.items/total`，price 为两位小数字符串 | ✅ `total: 14`，`price: "5.50"` |
| `GET /api/products/999999` | 404 | ✅「商品不存在」 |
| `POST /api/categories`（重名） | 409 | ✅「分类名称已存在」 |
| `PATCH /api/categories/{id}`（改成已存在名） | 409 | ✅同上 |
| `DELETE /api/categories/{有商品的分类}` | 409 | ✅「分类下有其他商品，不能删除分类」 |
| `POST /api/products`（price 三位小数） | 422 + 字段级报错 | ✅ |
| `GET /api/categories/statistics` | 各分类商品数（含 0） | ✅ 与列表统计一致 |
| CORS 预检（Origin: 5173） | 响应带 `access-control-allow-origin` | ✅ |

## 4. 设计与视觉核对

| 项 | 设计要求 | 实测 | 结论 |
| --- | --- | --- | --- |
| 统计卡高度 | 92px | 92px（label 13/18 + value 28/32 + hint 12/16 + padding 13） | ✅ |
| 表头 / 行高 | 44 / 48 | 44 / 48 | ✅ |
| 价格与库存对齐 | 右对齐 + tabular-nums | 一致 | ✅ |
| 状态色 | 上架绿 / 下架灰，红只给删除与库存 0，橙只给 1–20 | 一致（库存 0 红、12/20 橙、>20 正文色） | ✅ |
| 概览第二行 | 三块内容、底边对齐、无半行裁切 | 三卡 bottom 均 435，库存预警 4 行完整 44px | ✅ |
| 首屏高度 | 1440×900 无纵向滚动 | `scrollHeight = 900` | ✅ |
| 文案格式 | ¥x.xx / `yyyy-MM-dd HH:mm:ss` / 空值「—」 | 一致 | ✅ |

## 5. 本轮发现并修复的问题

| # | 问题 | 定位 | 处理 |
| --- | --- | --- | --- |
| D-01 | 统计卡 value 用 `line-height:1.25`，实际高度 ~35px，撑破 92px 预算 | `src/styles/index.css` 的 `.stat-card` | 改为 label 13/18、value 28/32、hint 12/16，实测 92px |
| D-02 | 概览左列「各分类商品数」下方空白 ~270px，右列比左列高 | `Dashboard.vue` + `.dash-grid` | 第一轮改 `stretch` 导致分布条之间出现空洞，**回退**后改为三列等宽等高栅格 |
| D-03 | 库存预警卡把第 3/4 条切成半行（滚动区高度非行高整数倍） | `.stock-warning__list` | 去掉内部滚动，行高固定 44px，4 条自然展开，三卡底边对齐 |
| D-04 | 验收脚本首轮 3 项失败（15/18）：删除确认按钮文案是「删除」不是「确定」；分类名 `E2E测试分类` 与 `E2E测试分类2` 子串互相误命中 | 验收脚本 | 修脚本（非产品缺陷），复跑 18/18 |
| D-05 | 首轮 UI-08 搜到 2 条 | 脚本 + 上次残留脏数据 | 清理残留数据后重跑通过 |

> D-02/D-03 说明：一次"看起来只是留白"的问题，改法不当会引出更严重的裁切；这类版式问题必须以 DOM 实测（bottom 坐标、行高、scrollHeight）验收，不能只看截图"差不多"。

## 6. 未覆盖范围

| 项 | 原因 | 建议 |
| --- | --- | --- |
| 商品 > 100 条时的概览统计 | 后端无按状态聚合接口，前端只取前 100 条 | v1.1 加 `/api/products/statistics` |
| 并发编辑冲突 | PATCH 提交整表单 | 改 diff 提交或加乐观锁 |
| 登录/权限、批量操作、导出 | v1 非目标（PRD 第 9 章） | 见 PRD 10.2 v1.1 候选 |
| 移动端适配 | 桌面优先（≥1280） | 需要时单独做响应式方案 |
| 前端组件单测 | 以端到端脚本覆盖 P0 交互 | 补 Vitest + Vue Test Utils |

## 7. 复核方式（任何人可重跑）

```bash
# 1) 后端
cd python/fastapi-demo && make check   # 期望 ruff 全过 + 23 passed

# 2) 起服务
cd python/fastapi-demo && uvicorn app.main:app --port 8000 &
cd fullstack/product-admin && pnpm dev &

# 3) 端到端
cd fullstack/product-admin && pnpm acceptance   # 期望最后一行「汇总：18/18 通过」
```
