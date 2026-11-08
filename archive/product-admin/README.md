# 归档：product-admin（商品管理模块）

这里存放 **2026-11-08 之前** 的「商品管理后台」全部资产。它们**不参与构建、不进 CI、不被打进镜像**，只在需要参考或恢复时使用。

为什么归档、代价与被否方案见 [ADR-0007](../../docs/adr/0007-archive-product-module.md)。

## 里面有什么

| 路径 | 内容 |
|---|---|
| `frontend/views/` | 商品列表、分类管理、概览三个页面（Vue SFC） |
| `frontend/components/` | 商品弹窗、分类弹窗、统计卡片 |
| `frontend/api/` | 商品 6 个、分类 5 个接口封装与它们的单测 |
| `frontend/types/product.ts` | 商品 / 分类的 TS 类型（已从 `frontend/src/types/api.ts` 拆出） |
| `frontend/styles/product-admin.css` | 统计卡、表格、状态标签、弹窗等页面样式（已从 `index.css` 拆出） |
| `frontend/scripts/acceptance.mjs` | 商品模块 18 项端到端验收脚本 |
| `backend/app/api/` | `products.py`、`categories.py` |
| `backend/app/services/` | `product_service.py`、`category_service.py` |
| `backend/app/schemas/` | `product.py`、`category.py` |
| `backend/app/models/` | `product.py`、`category.py` |
| `backend/app/seed.py` | 演示数据脚本（12 件商品 / 3 个分类） |
| `backend/tests/` | 商品与分类的服务层、接口层、Schema 单测（43 例） |
| `docs/prd.md` 等 | 需求（PRD）、设计规范与设计稿、验收说明、旧 API 契约 |
| `docs/design/mockups/` | 5 张可交互 HTML 设计稿 |
| `docs/shot-*.png` | 商品模块的实机截图 5 张 |

## 如何恢复（如果真要做）

1. 代码：把 `frontend/*` 放回 `frontend/src/*` 对应目录，`backend/*` 放回 `backend/app/*` 与 `backend/tests/`。
2. 表：`cd backend && alembic downgrade 17fe0c7d2cb5`（重建空的 `products` / `categories` 结构），或从备份恢复数据。
3. 入口：`backend/app/api/__init__.py` 重新 `include_router`，`frontend/src/router/index.ts` 加回路由，`App.vue` 加回菜单项。
4. 依赖与门禁：把 `frontend/types/product.ts` 的类型并回 `api.ts`、把 `product-admin.css` 追加回 `index.css`、`package.json` 加回 `acceptance` 脚本。
5. 文档：按当时的 PRD 与设计稿恢复 `docs/` 对应章节（注意它们已归档，不要直接当成现状）。

## 注意

- 这里的代码**不会被任何检查覆盖**，与当前 `frontend/`、`backend/` 的接口、类型、样式已经脱节，直接复制回去大概率要改。
- 不要把这里的内容重新 import 到主应用里——那会让归档重新变成维护负担。
