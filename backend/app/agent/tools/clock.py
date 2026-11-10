"""时间工具：模型没有时钟，问「现在几点」必须查。

返回带时区的时间，避免用户分不清本地时间与 UTC。
"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

from app.agent.tools.base import ToolError, spec_of

DEFAULT_TIMEZONE = "Asia/Shanghai"


class NowArgs(BaseModel):
    timezone: str = Field(
        default=DEFAULT_TIMEZONE,
        max_length=64,
        description="IANA 时区名，例如 Asia/Shanghai、UTC；不确定就省略，默认本地时区",
    )


class NowTool:
    name = "now"
    description = (
        "获取当前日期与时间（含星期）。用户问「现在几点/今天几号」时用它，不要凭记忆回答。"
    )
    args_model = NowArgs

    def spec(self) -> dict[str, Any]:
        return spec_of(self)

    def run(
        self,
        args: BaseModel,
        user_id: int,  # noqa: ARG002 —— 这两个工具不读用户数据，签名统一保留
    ) -> str:
        assert isinstance(args, NowArgs)
        try:
            zone = ZoneInfo(args.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ToolError(f"未知时区：{args.timezone}") from exc
        moment = datetime.now(zone)
        weekday = "一二三四五六日"[moment.weekday()]
        return moment.strftime(f"%Y-%m-%d %H:%M:%S %Z（星期{weekday}）")
