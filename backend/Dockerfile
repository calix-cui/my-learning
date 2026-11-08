# syntax=docker/dockerfile:1
# 后端镜像：依赖装进独立虚拟环境，运行层只带 venv 与源码。
# 构建前提：仓库里已有 uv.lock（`uv lock` 生成），否则导出会失败。

# ---------- 依赖层 ----------
FROM python:3.12-slim AS deps

# 只用 uv 做「导出锁文件」这件事；实际安装交给 pip（原因见下方注释）
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /uvx /usr/local/bin/

ENV UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app
# 只拷依赖声明，源码改动不会让这一层缓存失效
COPY pyproject.toml uv.lock ./

# 安装源可选：默认官方 PyPI，国内可换成镜像加速：
#   docker compose build --build-arg PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# 为什么是「uv export + pip」而不是 `uv sync`：
#   uv.lock 仍是唯一的版本来源（导出的 requirements 带 --hash，pip 会按哈希校验）；
#   但在部分环境（本机 colima VM + BuildKit）里 uv 并发下载 wheel 会长时间挂起，
#   而 pip 走同一个镜像源可以稳定装完。换到网络正常的环境可改回 `uv sync --frozen --no-dev`。
RUN python -m venv /opt/venv \
    && uv export --frozen --no-dev --no-emit-project --format requirements-txt -o /tmp/requirements.txt \
    && /opt/venv/bin/pip install --require-hashes -r /tmp/requirements.txt

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
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"

# 启动先跑迁移再起服务：容器第一次创建时表结构自动补齐，重复启动是幂等的
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
