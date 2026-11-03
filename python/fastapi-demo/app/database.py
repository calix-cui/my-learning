# database.py 定义连接入口与 ORM 基类
from datetime import datetime

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url)
# create_engine() 返回 Engine，后续通过它获取数据库连接
SessionLocal = sessionmaker(bind=engine)
# sessionmaker() 创建固定使用当前 Engine 的 Session 工厂，每次调用 SessionLocal() 得到新的 Session，不让全部请求共用同一个 Session

class Base(DeclarativeBase):
    # Base 继承 SQLAlchemy 的 DeclarativeBase，作为本项目所有 ORM 模型的共同基类
    # 它会收集后面模型定义的表信息，供建表时使用
    # 这里的 Base 本身不对应一张表；后面的分类表、商品表会分别获得自己的 id 和 create_time 列，不是共用同一条记录或一套 ID。
    id: Mapped[int] = mapped_column(
        # Mapped[int] 表示这个属性映射到数据库字段，Python 侧按整数使用
        # mapped_column() 配置字段的数据库类型和约束
        # 未显式提供数据库类型时，SQLAlchemy 可以根据 Mapped 中的 Python 类型推断，例如 int 对应整数
        primary_key=True, autoincrement=True, sort_order=-1, comment="主键ID"
        # autoincrement=True 表示由数据库生成自增 ID
        # sort_order=-1 让它排在默认排序值为 0 的其他字段之前，因此两张表建表时都会将 id 放在第一列
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="创建时间"
    )
# 创建 Engine 对象本身通常还不会连接 MySQL，真正执行建表或查询时才需要建立连接。因此，导入这个文件成功并不能证明数据库连接成功
