# fastapi-demo 常用命令入口：不用记长命令，make <目标> 即可
# 约定：依赖由 uv 管理（pyproject.toml + uv.lock），虚拟环境放在项目目录下（.venv）；
#       Python 解释器用 PY 变量覆盖，例如 make test PY=python3
PY ?= .venv/bin/python
UV ?= uv

.PHONY: help install install-dev lock run init-db migrate revision check-migration test lint fmt check clean-demo clean-demo-yes

help:  ## 列出所有命令
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## 按 uv.lock 安装全部依赖（含 ruff / pytest / pre-commit）
	$(UV) sync

install-dev: install  ## 兼容旧命令名，等价于 make install

lock:  ## 改了 pyproject.toml 的依赖后重新解析并更新 uv.lock
	$(UV) lock

run:  ## 启动开发服务器（热重载，http://127.0.0.1:8000/docs）
	$(PY) -m uvicorn app.main:app --reload

init-db:  ## 建库后把表结构升到最新版本（等价于 migrate，保留旧命令名）
	$(PY) -m app.init_db

migrate:  ## 应用所有未执行的迁移（alembic upgrade head）
	$(PY) -m alembic upgrade head

revision:  ## 按当前 ORM 模型生成迁移文件，用法：make revision m="add user table"
	@test -n "$(m)" || { echo '缺少提交说明，用法：make revision m="新增 xxx 表"'; exit 1; }
	$(PY) -m alembic revision --autogenerate -m "$(m)"

check-migration:  ## 确认 ORM 模型与迁移脚本一致（需要能连上 MySQL）
	$(PY) -m alembic check

test:  ## 运行测试并检查覆盖率（不需要 MySQL，门槛 80%）
	$(PY) -m pytest

lint:  ## 静态检查（只报告，不改文件）
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

fmt:  ## 自动修复导入顺序并格式化代码
	$(PY) -m ruff check --fix .
	$(PY) -m ruff format .

clean-demo:  ## 删掉本地库里 E2E/调试留下的示例账号（先看，再 --yes 真删）
	$(PY) scripts/cleanup_demo_accounts.py
	@echo '确认无误后执行： make clean-demo-yes'

clean-demo-yes:  ## 真的删除示例账号（会级联删掉它们的会话/消息/run）
	$(PY) scripts/cleanup_demo_accounts.py --yes

check: lint test  ## 提交前自检：lint + 测试（不需要数据库，CI 也跑这个）
