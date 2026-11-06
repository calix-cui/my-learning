# 来源与升级说明

- 上游：https://github.com/ejirocodes/agent-skills
- 路径：`vue/skills/vue-best-practices/`
- 引入 commit：`6e805e4cc8a4378444c791d4a08e304347152bd0`
- 引入日期：2026-11-06
- 许可：MIT（见同目录 `LICENSE`，版权归 ejirocodes）
- 本地修改：**仅一处**——在 `SKILL.md` frontmatter 之后插入「本项目适配」段落（声明技术栈与「新增依赖先说明」的约束）；`references/` 与其余正文未改

## 与其他候选的对比

同时候选还有 `dkbnull/hello-skill` 的 `frontend/skills/vue`（中文、单文件、114 行，偏「强制约束」风格）。
未采用的原因：它要求 Pinia、`unplugin-auto-import`、`vite-plugin-vue-devtools`、Authorization 拦截器等本项目并不存在的东西，会诱导 agent 擅自引入依赖。
本 skill 以「事实与工具链坑」为主（Volar、vue-tsc、props 提取、defineModel），冲突面更小。

## 升级方式

```bash
B=https://raw.githubusercontent.com/ejirocodes/agent-skills/main/vue/skills/vue-best-practices
curl -sSL "$B/SKILL.md" -o /tmp/vb.new.md
diff .agents/skills/vue-best-practices/SKILL.md /tmp/vb.new.md
```
