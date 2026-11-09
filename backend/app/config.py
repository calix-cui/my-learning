# 读取连接信息
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# BaseSettings 是 pydantic-settings 提供的配置基类，已经实现了读取配置、匹配字段和校验类型的功能
# class Settings(BaseSettings): 表示让自己的 Settings 类继承这些功能，不需要再手动打开配置文件、查找字段并逐项校验。
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # 校验失败时不回显输入值，避免把 LLM_API_KEY 之类的密钥打进日志
        hide_input_in_errors=True,
    )

    database_url: str

    # 模型接入（阶段 4）。默认 fake：CI 与没有 key 的本地环境都能跑通整条链路。
    llm_provider: Literal["fake", "openai"] = "fake"
    llm_base_url: str = ""
    llm_api_key: SecretStr = SecretStr("")  # SecretStr 让日志/报错里显示为 **********
    llm_model: str = ""
    llm_timeout_seconds: float = 30.0
    # 假模型每块的延迟：本地演示流式效果时调大一点（默认 0，测试不受影响）
    llm_fake_delay_seconds: float = 0.0

    # 账号体系（阶段 4.5）。allow_registration=false 时注册接口直接返回 403，
    # 适合部署到公网后只允许管理员用脚本建号。
    allow_registration: bool = True
    session_ttl_days: int = 30
    # development / production。production 下会话 Cookie 才会带 Secure（要求 https）
    app_env: str = "development"

    @model_validator(mode="after")
    def _check_openai_settings(self) -> "Settings":
        """选 openai 时，缺 base_url / key / model 直接在启动阶段失败，而不是等第一次请求。"""
        if self.llm_provider != "openai":
            return self
        missing = [
            name
            for name, value in (
                ("LLM_BASE_URL", self.llm_base_url),
                ("LLM_API_KEY", self.llm_api_key.get_secret_value()),
                ("LLM_MODEL", self.llm_model),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"LLM_PROVIDER=openai 时必须配置：{', '.join(missing)}")
        return self


# database_url: str 声明需要一个字符串类型的配置字段。
# BaseSettings 根据字段名匹配配置，默认不区分环境变量名的大小写，因此它会将 DATABASE_URL 的值赋给 database_url。这个字段没有默认值，如果配置中缺少它，创建配置对象时就会报校验错误。
# SettingsConfigDict 指定读取 .env 并使用 UTF-8 编码
# 这个相对路径以运行命令时所在的目录为基准，所以本篇命令都在项目根目录执行。系统环境变量中的同名配置优先于 .env
# 修改文件后发现仍连接旧地址时，也要检查终端是否设置过同名环境变量。规则见 Pydantic Settings 文档（官方英文）。

settings = Settings()
# 执行 settings = Settings() 时，才会按照上面的声明加载配置、匹配字段并校验类型，创建配置对象。
# 这里会读取 .env 中的 DATABASE_URL，按 str 类型校验后保存到 settings.database_url。
# 其他模块导入 settings，就能通过这个属性取得连接字符串。
