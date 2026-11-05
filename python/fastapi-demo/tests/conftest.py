"""测试公共配置。

app.config.Settings 的 database_url 没有默认值，缺少配置时 import app 直接抛校验错误。
测试不连接数据库（只覆盖参数校验、响应模型、异常处理），因此这里给一个占位连接串：
create_engine 是惰性的，只要不真正查询，就不会去连 127.0.0.1:3306。
"""

import os

os.environ.setdefault(
    "DATABASE_URL",
    "mysql+pymysql://test:test@127.0.0.1:3306/fastapi_demo_test?charset=utf8mb4",
)
