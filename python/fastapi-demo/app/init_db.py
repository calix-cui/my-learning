# init_db.py 是本篇手动运行的建表入口
from app import models  # noqa: F401  # 导入即注册模型，下面的 create_all 依赖这次副作用
from app.database import Base, engine

# from app import models 会导入 app/models.py
# 首次导入时，Python 会执行该文件的顶层代码，包括 Category、Product 的类定义
# 两个类继承了 Base，SQLAlchemy 会在创建这些模型类时，根据字段声明生成表结构描述，并登记到同一个 Base.metadata 中
# 这里登记的是内存中的表定义，还没有在 MySQL 中建表。


def main():
    """根据已经注册的模型，在数据库自动创建表"""
    print("开始执行创建表的脚本")
    Base.metadata.create_all(bind=engine)
    print("相关的表已经创建成功")


# 这段代码的执行顺序是：
# 导入 models，执行模型类定义，将 categories、products 的表定义登记到 Base.metadata。
# 调用 Base.metadata.create_all(bind=engine)，通过 Engine 连接数据库，检查并创建尚不存在的表。
# 建表调用成功后，输出完成提示。

# create_all() 只处理已经登记的表定义，不会自动查找项目中的模型文件
# 因此，虽然下面没有直接使用 models 变量，这个导入仍需保留。本篇如果省略它，两个模型尚未加载，Base.metadata 中就没有对应的表定义，create_all() 也不会创建这两张表
# 它也不会创建 fastapi_demo 这个数据库，因此第 2 部分的建库步骤不能省略。

# 仅在主动运行此模块时建表，被其他模块导入时不执行。
if __name__ == "__main__":
    main()
