# 归档文档

这里的文档是**阶段性产物**，结论已经并入正式文档，保留仅为考古与追溯。

| 文档 | 是什么 | 结论去了哪里 |
|---|---|---|
| [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) | 2026-11-07 项目现状盘点（149 行，含目录树、规模基线、能力清单） | [`../how-it-works.md`](../how-it-works.md)、[`../PROJECT_STATUS.md`](../PROJECT_STATUS.md) |
| [`AI_ENVIRONMENT_AUDIT.md`](AI_ENVIRONMENT_AUDIT.md) | 同日的 AI 开发环境审计（Skills、MCP、CLI 矩阵、项目级 Skill 扫描根实测） | [`../agents/README.md`](../agents/README.md) §6、[`../toolchain.md`](../toolchain.md) |
| [`REUSE_CANDIDATES.md`](REUSE_CANDIDATES.md) | 8 组技术选型调研（版本、维护状态、结论、Top 5） | 前端门禁 → [ADR-0002](../adr/0002-frontend-quality-gate-lite.md)；测试分层 → [ADR-0005](../adr/0005-testing-baseline.md)；桌面端 → [ADR-0001](../adr/0001-desktop-shell-electron.md)；依赖管理 → `pyproject.toml` / `uv.lock` / `package.json` |

三份报告的「Top 5 优先事项」执行结果：Alembic 迁移 → [ADR-0003](../adr/0003-database-migrations-alembic.md) ✅；前端轻量门禁 → [ADR-0002](../adr/0002-frontend-quality-gate-lite.md) ✅；uv 统一依赖 ✅；Docker 化部署 → [ADR-0004](../adr/0004-deployment-docker-compose.md) ✅；测试基线 → [ADR-0005](../adr/0005-testing-baseline.md) ✅。

**归档规则**：不再更新这里的内容。如果发现结论过期，改对应的正式文档，不要改归档。
