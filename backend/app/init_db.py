# init_db.py 是本篇手动运行的建表入口（已改为执行 Alembic 迁移）
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


def main():
    """把数据库升级到最新迁移版本（等价于 `alembic upgrade head`）"""
    print("开始执行数据库迁移")
    config = Config(str(ALEMBIC_INI))
    # 用绝对路径，避免从其他工作目录调用时找不到 migrations/
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    # upgrade 是幂等的：库已经是最新版本时不会重复执行任何 DDL
    command.upgrade(config, "head")
    print("数据库迁移完成，表结构已是最新版本")


# 迁移脚本在 migrations/versions/ 下，按 revision 链依次执行；
# 每个版本都在 alembic_version 表里留一条记录，因此重复运行是安全的。
# 新增字段或表之后，用 `make revision m="说明"` 生成新的迁移文件，
# 再执行 `make migrate` 应用——不要再直接用 Base.metadata.create_all()，
# 它只建缺失的表，不会修改已有表结构，也不会留版本记录。

# 仅在主动运行此模块时执行迁移，被其他模块导入时不执行。
if __name__ == "__main__":
    main()
