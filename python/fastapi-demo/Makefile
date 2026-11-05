# fastapi-demo 常用命令入口：不用记长命令，make <目标> 即可
# 约定：虚拟环境放在项目目录下（.venv），Python 解释器用 PY 变量覆盖，例如 make test PY=python3
PY ?= .venv/bin/python

.PHONY: help install install-dev run init-db test lint fmt check

help:  ## 列出所有命令
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## 安装运行时依赖
	$(PY) -m pip install -r requirements.txt

install-dev:  ## 安装开发依赖（含 ruff / pytest / pre-commit）
	$(PY) -m pip install -r requirements-dev.txt

run:  ## 启动开发服务器（热重载，http://127.0.0.1:8000/docs）
	$(PY) -m uvicorn app.main:app --reload

init-db:  ## 按 ORM 模型建表（需先有数据库和 .env）
	$(PY) -m app.init_db

test:  ## 运行测试（不需要 MySQL）
	$(PY) -m pytest

lint:  ## 静态检查（只报告，不改文件）
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

fmt:  ## 自动修复导入顺序并格式化代码
	$(PY) -m ruff check --fix .
	$(PY) -m ruff format .

check: lint test  ## 提交前自检：lint + 测试
