# syntax=docker/dockerfile:1
# 后端镜像：依赖用 uv 装进独立虚拟环境，运行层只带 venv 与源码。
# 构建前提：仓库里已有 uv.lock（`uv lock` 生成），否则 --frozen 会失败。

# ---------- 依赖层 ----------
FROM python:3.12-slim AS deps

COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
# 只拷依赖声明，源码改动不会让这一层缓存失效
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ---------- 运行层 ----------
FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app
COPY --from=deps /opt/venv /opt/venv
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app app ./app

USER app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"

# 启动先跑迁移再起服务：容器第一次创建时表结构自动补齐，重复启动是幂等的
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
