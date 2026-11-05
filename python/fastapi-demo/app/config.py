# 读取连接信息
from pydantic_settings import BaseSettings, SettingsConfigDict


# BaseSettings 是 pydantic-settings 提供的配置基类，已经实现了读取配置、匹配字段和校验类型的功能
# class Settings(BaseSettings): 表示让自己的 Settings 类继承这些功能，不需要再手动打开配置文件、查找字段并逐项校验。
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    database_url: str


# database_url: str 声明需要一个字符串类型的配置字段。
# BaseSettings 根据字段名匹配配置，默认不区分环境变量名的大小写，因此它会将 DATABASE_URL 的值赋给 database_url。这个字段没有默认值，如果配置中缺少它，创建配置对象时就会报校验错误。
# SettingsConfigDict 指定读取 .env 并使用 UTF-8 编码
# 这个相对路径以运行命令时所在的目录为基准，所以本篇命令都在项目根目录执行。系统环境变量中的同名配置优先于 .env
# 修改文件后发现仍连接旧地址时，也要检查终端是否设置过同名环境变量。规则见 Pydantic Settings 文档（官方英文）。

settings = Settings()
# 执行 settings = Settings() 时，才会按照上面的声明加载配置、匹配字段并校验类型，创建配置对象。
# 这里会读取 .env 中的 DATABASE_URL，按 str 类型校验后保存到 settings.database_url。
# 其他模块导入 settings，就能通过这个属性取得连接字符串。
