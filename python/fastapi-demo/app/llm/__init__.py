"""模型客户端入口：按配置选择实现，并提供 FastAPI 依赖。

业务代码统一 `from app.llm import get_llm`，测试里用
`app.dependency_overrides[get_llm] = lambda: FakeLLM(...)` 直接替换。
"""

from functools import lru_cache

from app.config import settings
from app.llm.base import ChatMessage, LLMClient, LLMError, LLMReply, LLMTimeoutError
from app.llm.fake import FakeLLM
from app.llm.openai_compatible import OpenAICompatibleClient

__all__ = [
    "ChatMessage",
    "LLMClient",
    "LLMError",
    "LLMReply",
    "LLMTimeoutError",
    "build_llm",
    "get_llm",
]


def build_llm() -> LLMClient:
    """按 settings 构造实现。生产只缓存一次，避免每个请求新建 httpx 连接池。"""
    if settings.llm_provider == "openai":
        return OpenAICompatibleClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value(),
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return FakeLLM(delay_seconds=settings.llm_fake_delay_seconds)


@lru_cache
def get_llm() -> LLMClient:
    return build_llm()
