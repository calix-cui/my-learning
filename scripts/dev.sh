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

pids=""
cleanup() {
  trap - INT TERM EXIT

  for pid in $pids; do
    kill "$pid" 2>/dev/null || true
  done

  wait 2>/dev/null || true
  echo
  echo "[dev] 已停止。日志在 $LOG_DIR/"
}
trap cleanup INT TERM EXIT

echo "[dev] 后端 :${API_PORT}（改 backend/app 自动重启）"
(
  cd backend
  exec uv run --frozen --env-file .env uvicorn app.main:app \
    --reload --host 127.0.0.1 --port "$API_PORT"
) >"$LOG_DIR/api.log" 2>&1 &
pids="$pids $!"
api_pid=$!

echo "[dev] 前端 :${WEB_PORT}（Vite HMR）"
(
  cd frontend
  exec pnpm dev --port "$WEB_PORT" --strictPort
) >"$LOG_DIR/web.log" 2>&1 &
pids="$pids $!"
web_pid=$!

# 探测一个地址能不能响应。
# 关键：必须 --noproxy '*'。很多人 shell 里开着 http_proxy（Clash/Surge 之类），
# 此时 curl 对 127.0.0.1 也会走代理，代理返回 502，探测永远失败——
# 服务明明起来了，脚本却报「没在 60s 内就绪」。
probe_http() {
  local url=$1
  if command -v curl >/dev/null 2>&1; then
    curl -fs --noproxy '*' --max-time 2 -o /dev/null "$url" 2>/dev/null
    return $?
  fi
  # 没有 curl 就退回 TCP 探测：只看端口有没有人听
  local hostport=${url#*://}
  hostport=${hostport%%/*}
  (exec 3<>"/dev/tcp/${hostport%:*}/${hostport##*:}") 2>/dev/null
}

# 等两边起来再打印地址，避免把「还没起来」的地址贴给用户
wait_for() {
  local name=$1 url=$2 pid=$3 log=$4 timeout=${5:-60}
  local i
  for ((i = 1; i <= timeout; i++)); do
    if probe_http "$url"; then
      return 0
    fi
    # 进程已经退出就别傻等满 60 秒（端口被占用时最常见）
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "[dev] $name 进程已退出，日志末尾：" >&2
      tail -n 15 "$log" 2>/dev/null | sed 's/^/    /' >&2
      return 1
    fi
    sleep 1
  done
  echo "[dev] $name 没在 ${timeout}s 内就绪（$url），日志末尾：" >&2
  tail -n 15 "$log" 2>/dev/null | sed 's/^/    /' >&2
  return 1
}

# 起不来就退出（trap 会把另一个也收掉），不要留半套环境
READY_TIMEOUT="${READY_TIMEOUT:-90}"
wait_for "后端" "http://127.0.0.1:$API_PORT/healthz" "$api_pid" "$LOG_DIR/api.log" "$READY_TIMEOUT" || exit 1
wait_for "前端" "http://127.0.0.1:$WEB_PORT/" "$web_pid" "$LOG_DIR/web.log" "$READY_TIMEOUT" || exit 1

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
