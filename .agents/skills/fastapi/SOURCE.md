# 来源与升级说明

- 上游：https://github.com/fastapi/fastapi
- 路径：`fastapi/.agents/skills/fastapi/`
- 引入 commit：`1ca09c13584ca45aa0921e5e40b31d49c5e3135a`
- 引入日期：2026-11-06
- 许可：MIT（见同目录 `LICENSE`，版权归 Sebastián Ramírez）
- 本地修改：**仅一处**——在 `SKILL.md` frontmatter 之后插入「本项目适配」段落（说明 `fastapi==0.124.4` 下不可用的 `app.frontend()` / `fastapi.sse` / 原生 OpenTelemetry / `fastapi` CLI）；`references/` 与其余正文未改

## 升级方式

```bash
B=https://raw.githubusercontent.com/fastapi/fastapi/master/fastapi/.agents/skills/fastapi
# 覆盖前先 diff，确认上游变更后再替换
curl -sSL "$B/SKILL.md" -o /tmp/SKILL.new.md
diff .agents/skills/fastapi/SKILL.md /tmp/SKILL.new.md
```

升级后请同步更新本文件的 commit 与日期，以及 `docs/agents/README.md` 的清单表。
