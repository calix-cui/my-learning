#!/usr/bin/env bash
#
# 一条命令起本地开发环境：后端（uvicorn --reload）+ 前端（vite dev）。
# 两个进程都开着热更新，改代码即时生效；Ctrl-C 一次把两个都收掉。
#
# 用法：
#   ./scripts/dev.sh            # 后端 :8000，前端 :5173
#   API_PORT=8001 ./scripts/dev.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
LOG_DIR="$ROOT/.dev-logs"

cd "$ROOT"

die() {
  echo "[dev] $*" >&2
  exit 1
}

# 允许外部指定 uv 缓存目录（CI/沙箱里 ~/.cache 可能不可写）
export UV_CACHE_DIR="${UV_CACHE_DIR:-$HOME/.cache/uv}"

command -v uv >/dev/null 2>&1 || die "找不到 uv，先装：curl -LsSf https://astral.sh/uv/install.sh | sh"
command -v pnpm >/dev/null 2>&1 || die "找不到 pnpm，先装：npm i -g pnpm@12"

[ -f backend/.env ] || die "缺少 backend/.env，先执行：cp backend/.env.example backend/.env 并填 DATABASE_URL"
if [ ! -d frontend/node_modules ]; then
  echo "[dev] 前端依赖还没装，正在 pnpm install …"
  (cd frontend && pnpm install --frozen-lockfile)
fi

mkdir -p "$LOG_DIR"

pids=()
cleanup() {
  trap - INT TERM EXIT
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  echo
  echo "[dev] 已停止。日志在 $LOG_DIR/"
}
trap cleanup INT TERM EXIT

echo "[dev] 后端 :$API_PORT（改 backend/app 自动重启）"
(
  cd backend
  exec uv run --frozen --env-file .env uvicorn app.main:app \
    --reload --host 127.0.0.1 --port "$API_PORT"
) >"$LOG_DIR/api.log" 2>&1 &
pids+=($!)
api_pid=$!

echo "[dev] 前端 :$WEB_PORT（Vite HMR）"
(
  cd frontend
  exec pnpm dev --port "$WEB_PORT" --strictPort
) >"$LOG_DIR/web.log" 2>&1 &
pids+=($!)
web_pid=$!

# 等两边起来再打印地址，避免把「还没起来」的地址贴给用户
wait_for() {
  local name=$1 url=$2 timeout=${3:-60}
  for _ in $(seq 1 "$timeout"); do
    if curl -fs -o /dev/null --max-time 2 "$url" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  echo "[dev] $name 没在 ${timeout}s 内就绪，看日志：$LOG_DIR" >&2
  return 1
}

wait_for "后端" "http://127.0.0.1:$API_PORT/healthz" 60 || true
wait_for "前端" "http://127.0.0.1:$WEB_PORT/" 60 || true

cat <<EOF

  ┌───────────────────────────────────────────────┐
  │  前端  http://127.0.0.1:$WEB_PORT                  │
  │  接口  http://127.0.0.1:$API_PORT/docs             │
  │  日志  $LOG_DIR/api.log、web.log
  └───────────────────────────────────────────────┘
  改代码即生效；Ctrl-C 停止两个服务。

EOF

# 任一进程挂掉就把另一个也收掉，别留下半套环境
while kill -0 "$api_pid" 2>/dev/null && kill -0 "$web_pid" 2>/dev/null; do
  sleep 2
done

echo "[dev] 有进程退出，正在收拾另一个…" >&2
exit 1
