# 文档体系重构 · 终检报告

> **归档文档**：本报告是 2026-11-07 文档治理的收尾记录，结论已并入 `docs/README.md` 与 `docs/TECHNICAL_DEBT.md`。后续不必再读。

范围：阶段三（分批重构）与阶段四（终检）的实际执行结果。
基线：`8a3e806` → 终检：`473433d`（3 个重构提交 + 本报告）。

## 1. 结论

- **结构**：从「平铺 20 份 + 1 个孤儿目录」变为「人读 12 / AI 向 20 / 归档 4」三层，`docs/` 下 37 份 md（含本报告）全部可从 `docs/README.md` 一张地图找到，**0 孤儿**。
- **内容**：审计列的 22 条事实陈旧全部处理（19 条改正、3 条标注为历史证据）；A 类逐条可验证，无一条靠「大概」改。
- **关联**：全仓 markdown 相对链接 **0 失效**（改造前 0，改造后仍 0）；6 个 mermaid 代码块全部通过语法解析。
- **AI 协作**：`AGENTS.md` 有「当前交付物」与「任务 → 文档路由」，`docs/playbooks/` 有索引与标题，三层文档各有标注，归档有归档规则。
- **代价**：文档总行数从 4089 → 4201（+112），其中新增章节（how-it-works §7、toolchain §5、deploy §3.1、playbooks 索引）净增约 110 行；没有为了「看起来精简」删掉有效信息。

## 2. 结构变化

```
改造前（20 份平铺）                     改造后（三层）
docs/                                  docs/
├── README.md（10 行占位）              ├── README.md            入口：阅读路径 + 地图 + 单一来源
├── how-it-works.md                    ├── how-it-works.md      系统怎么跑（架构/时序/数据/新增资源）
├── toolchain.md                       ├── toolchain.md         工具怎么用（含测试全景 §5）
├── PROJECT_STATUS.md                  ├── PROJECT_STATUS.md    现在到哪一步
├── delivery.md                        ├── delivery.md          交付与验收
├── deploy.md                          ├── deploy.md            部署（含环境变量总表 §3.1）
├── api.md（在 python/ 下）      ←移   ├── api.md               接口契约（唯一来源）
├── project/TECHNICAL_DEBT.md    ←移   ├── TECHNICAL_DEBT.md    技术债（带证据与状态）
├── product/prd.md                     ├── product/prd.md       需求与验收
├── design/design.md                   ├── design/design.md     视觉规范
├── design/images/01..05-*.png   ←改   ├── design/images/design-*.png
├── images/01..05-*.png          ←改   ├── images/shot-*.png + diagram-*.png
├── adr/（5 篇 + 索引）                 ├── adr/（5 篇 + 索引）
├── agents/（6 份）                     ├── agents/（6 份）
├── prompts/（7 份，孤儿）        ←改   ├── playbooks/（7 份 + 索引，kebab-case + H1）
└── archive/（3 份）                    └── archive/（3 份 + 索引标注结论去向）
                                       + DOCUMENTATION_{AUDIT,REFACTOR_PLAN,FINAL_REPORT}.md
```

删除：`python/fastapi-demo/app/README.md`（9 行目录说明，并入 `how-it-works.md` §3）。

## 3. 四类检查

### 3.1 结构检查

| 检查项 | 方法 | 结果 |
|---|---|---|
| 每个文档有唯一职责 | 人工比对 `docs/README.md` 地图的「一句话」 | 无两两重复描述；接口/页面/错误码/命令各有唯一来源 |
| 无孤儿文档 | 脚本：`docs/**/*.md` 逐个在地图中查找 | 0 孤儿 |
| 目录层级不超 2 层 | `find docs -maxdepth 2` | 全部 ≤2 层 |
| 命名一致 | 人工 | 人读 `kebab-case.md`；playbooks `NN-name.md`；截图 `shot-*` / 设计稿 `design-*` / 图 `diagram-*` |
| 无空目录 | `find docs -type d -empty` | 无 |

### 3.2 内容检查（对代码复核）

全部用命令复跑，不凭记忆：

| 事实 | 文档写的 | 实测命令与结果 |
|---|---|---|
| 接口规模 | 11 业务 + 3 运维 | `app.openapi()` → 9 path / 14 operation |
| 后端用例 | 55 passed / 85.38% | `make check` → `55 passed`，`Total coverage: 85.38%` |
| 前端用例 | 17 | `pnpm test` → 17 passed |
| 端到端用例 | 18 项 | `scripts/acceptance.mjs` 的用例数组长度 18 |
| pre-commit 钩子 | 8 个 | `.pre-commit-config.yaml` → 8 个 `id:` |
| Compose 服务 | 4 个（含 caddy profile） | `docker-compose.yml` → db / backend / frontend / caddy |
| ADR 数量 | 5 篇 + 索引 | `ls docs/adr/*.md` → 6（5 篇 + README） |
| 商品/分类示例数据 | 12 商品 / 3 分类 | `GET /api/products/count` 与 seed 输出 |

### 3.3 关联检查

| 检查项 | 方法 | 结果 |
|---|---|---|
| 相对链接存在性 | 脚本遍历 42 份 md（剔除 `.agents/skills`）的 `[..](..)` | **0 失效** |
| 图片引用 | 同上，含 `.png` 目标 | 0 失效（改名后全部命中） |
| 交叉引用有效性 | 抽查「`docs/README.md` §4 单一来源」8 行指向 | 8/8 目标章节存在 |
| mermaid 语法 | `mermaid.parse()` 逐块 | 6 块全部 OK |
| 索引完整性 | `docs/adr/README.md`、`docs/agents/README.md`、`docs/playbooks/README.md`、`docs/archive/README.md` | 每份子文件都在索引中 |

### 3.4 AI 协作检查

| 检查项 | 结果 |
|---|---|
| 入口指引 | `AGENTS.md` §0 说明「当前交付是商品管理后台，不是 Agent 应用」，§8 给 7 类任务的必读文件；`docs/README.md` §1 给 3 条人类阅读路径 |
| 规则与文档边界 | `AGENTS.md`（怎么干活）、`docs/agents/`（角色分工）、`.agents/skills/`（领域规范）、`docs/adr/`（为什么这么定）四者职责不重叠，`docs/agents/README.md` §6 写明出处规则 |
| 文档分层标注 | 人读文档无标注；`AGENTS.md`/`adr/`/`agents/`/`playbooks/` 顶部有「AI 向文档」；`archive/` 顶部有「归档文档」 |
| 无冲突表述 | 审计的 X-01（编辑只提交 stock）已按实现改 PRD；X-02（Caddy 未实测）已在 `deploy.md` §10 标注，其余 X-03…X-08 均已在批 1–3 处理 |

## 4. 去重结果（人读 12 份范围内统计）

| 重复事实 | 改造前 | 改造后 | 处理方式 |
|---|---|---|---|
| 接口清单 | 3 处（api.md / 后端 README / PRD） | 1 处（`docs/api.md`）+ 后端 README 一行汇总 | 后端 README 12 行表压成 1 句 + 链接 |
| 页面功能清单 | 3 处（PRD / design / 前端 README） | 2 处（PRD 管需求、design 管视觉）+ 前端 README 只留路由表 | 前端 README 降级为路由表 |
| 文档分层规则 | 2 处（docs/README §3-5 / CONTRIBUTING） | 1 处（docs/README），CONTRIBUTING 只留 3 条并链接 | CONTRIBUTING 删表 |
| 目录职责 | 3 处（app/README / 后端 README / how-it-works） | 1 处（how-it-works §3） | 删 app/README |
| `make check` 命令 | 10 份提到 | 7 份（都是「该命令在本项目怎么跑」的局部语境） | 不再强行合并——命令出现在不同上下文属于合理重复 |
| `18 项 E2E` | 9 份提到 | 4 份 | 验收结果归 `delivery.md`，其余改为链接或删句 |

## 5. 未做与原因

| 事项 | 状态 | 原因 |
|---|---|---|
| `scripts/check-docs.mjs` | **未落地**，待你决定 | 收益：链接失效与过期数字能被 CI 拦住；成本：多一个约 60 行脚本 + 一个 CI job，且「过期数字」需要维护一份正则黑名单，容易误报。当前人工检查一次约 1 分钟，文档月更频率下未必划算。建议：先观察两次改动，若再出现链接失效或数字漂移再加 |
| Caddy / HTTPS 实测 | 未做 | 你已明确「先不管 Caddy/HTTPS」；`deploy.md` §10 已标注「未实测」 |
| `docs/archive/*` 内容纠错 | 未做 | 归档规则：只保留历史原貌，过期结论指向正式文档 |
| 把 `diagram-*.png` 的生成脚本入库 | 未做 | 图已标注「权威版本是 md 里的 mermaid 代码块」，PNG 只是快照；把 puppeteer 渲染脚本入库会引入额外依赖，收益不足 |
| PRD AC-08 改实现而非文档 | 按你的判断处理 | 你指出「改商品只提交 stock 不合理」，故改 PRD 与实现对齐，代码未动 |

## 6. 剩余风险

1. **过期数字仍会漂移**：单测数量、覆盖率、接口数量写死在 6 份文档。没有自动校验（见 §5 Q6），下一次改测试时容易漏改。缓解：这些数字现在只允许出现在 `PROJECT_STATUS.md` 与 `delivery.md`（`docs/README.md` §4 已写入规则），其余处引用。
2. **`docs/api.md` 与代码仍可能脱节**：契约靠人维护，后端没有「从 OpenAPI 生成文档」的流程。缓解：`api.md` 头部已写「改接口必须同时改这里」；CI 不校验。
3. **`playbooks/` 的 7 份说明书是历史产物**：内容针对「从 0 到 1」阶段，阶段 2 之后可能需要重写，届时按 §3.1 的命名规则新增而非覆盖。
4. **ADRs 只增不改**：若未来推翻 Electron 决策，正确做法是新增 `0006-…`，在旧 ADR 标「已被 0006 取代」，不要改历史记录。

## 7. 复核方法（任何人都能重跑）

```bash
# 1. 链接与图片
python3 - <<'PY'
import re, pathlib
root = pathlib.Path('.')
bad = []
for md in root.rglob('*.md'):
    if '.agents' in md.parts: continue
    for m in re.finditer(r'\[[^\]]*\]\(([^)\s]+)\)', md.read_text(errors='ignore')):
        t = m.group(1)
        if t.startswith(('http', 'mailto:', '#')): continue
        t = t.split('#')[0]
        if t and not (md.parent / t).exists():
            bad.append(f'{md}: {t}')
print('失效链接:', len(bad)); print('\n'.join(bad))
PY

# 2. 测试与覆盖率（文档里写的 55 / 85.38%）
cd python/fastapi-demo && make check

# 3. 接口规模（文档写的 11 + 3）
cd python/fastapi-demo && .venv/bin/python -c "from app.main import app; s=app.openapi(); print(len(s['paths']), [(p,m) for p,v in s['paths'].items() for m in v if m in ('get','post','patch','delete')][:3])"

# 4. 前端门禁
cd fullstack/product-admin && pnpm lint && pnpm test && pnpm build
```
