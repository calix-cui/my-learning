# ADR-0001：桌面端外壳选择 Electron

> **AI 向文档**：架构决策记录，人与 AI 共读；每条决策的「为什么」是重点。总入口见 [`../README.md`](../README.md)。

- **状态**：已接受（Accepted）
- **日期**：2026-11-06
- **决策人**：项目 owner（用户）
- **影响范围**：桌面端方案、打包链路、后续 `desktop/` 目录结构

## 背景

AGENTS.md §5 要求最终支持 macOS / Windows / Linux 三平台桌面客户端，并要求「尽可能复用 Web 前端和后端能力，避免维护三套独立业务实现」。

阶段 1 的选型调研（见 [REUSE_CANDIDATES §7](../archive/REUSE_CANDIDATES.md)）对比了三种外壳：

| 候选 | 壳 | 体积 | 复用现有 Vue 产物 | 拉起本地 Python 后端 |
|---|---|---|---|---|
| Tauri v2 | Rust + 系统 WebView | 小 | 可以 | 需 `externalBin` sidecar，二进制要按 target-triple 命名 |
| Electron | Chromium + Node | 大 | 可以 | `child_process.spawn` 最直接 |
| Wails | Go + 系统 WebView | 中 | 可以 | 无一等 Python sidecar 机制 |

调研结论原本倾向 Tauri（包体小、官方 sidecar 机制成熟）。**项目 owner 决定采用 Electron**。

## 决策

**桌面端外壳使用 Electron**，后续新增 `desktop/` 目录，构建产物复用 `frontend` 的 `vite build` 输出，Python 后端以子进程方式随应用启动。

## 理由

1. **拉起 Python 后端最简单**：Electron 主进程直接 `child_process.spawn` 打包后的后端可执行文件，只需管理端口与生命周期；Tauri 要维护 Rust 侧的 sidecar 配置、目标三元组命名、每平台各自构建。
2. **构建链只多一层 Node**：现有的 pnpm/Vite/TypeScript 工具链可以原样复用，不需要引入 Rust 工具链（这是 Tauri 的主要隐性成本）。
3. **调试与排障成本低**：主进程/渲染进程都能用 Chrome DevTools 调试，问题能搜到答案（符合 AGENTS.md「能搜到答案」的约束）。
4. **打包生态成熟**：electron-builder 覆盖三平台安装包、自动更新、代码签名，不用自己拼。

## 接受的成本（已知代价）

- **包体显著变大**：量级 100MB+（本项目**未实测**，仅作量级提示）。
- **内存占用高**：每个窗口一个 Chromium 渲染进程。
- **打包与签名更重**：macOS 需要 notarization，Windows 需要代码签名证书。
- **需要保持 Chromium 安全更新**：Electron 大版本升级节奏要跟。

## 备选方案（存档）

Tauri v2 仍是**技术上更轻**的方案，若后续出现「安装包体积是硬约束」或「需要极致冷启动」的需求，可在 `desktop/` 尚未成型前重新评估。评估触发条件：桌面端首次对外分发前、或包体被明确列为验收指标时。

## 后续待定（本 ADR 不覆盖）

- 后端如何打包进桌面（PyInstaller `--onedir` vs 其它）——见 REUSE_CANDIDATES §7，倾向 PyInstaller onedir。
- 本地后端鉴权（随机端口 + 一次性 token）。
- 自动更新通道与签名证书来源。
