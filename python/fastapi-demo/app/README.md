# 目录说明

api	定义路径、接收请求、调用业务函数，将结果或异常转换为 HTTP 响应
schemas	Pydantic 业务请求与响应模型，声明输入约束、输出字段及格式
common	共用的响应外壳、业务异常与全局异常处理函数
services	业务检查、数据库写入、提交与回滚
models	SQLAlchemy ORM 模型，描述数据库表和字段
database.py、dependencies.py	提供 Engine、公共 Base、Session 工厂及请求依赖
main.py	创建 FastAPI 应用，注册 API 路由与共用异常处理器
