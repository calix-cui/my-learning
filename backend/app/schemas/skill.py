from pydantic import BaseModel, Field


class SkillItem(BaseModel):
    slug: str = Field(description="稳定标识")
    name: str = Field(description="展示名")
    description: str = Field(description="一句话说明")
    tools: list[str] = Field(default_factory=list, description="工具白名单，空表示不限制")
    tool_count: int = Field(description="白名单里的工具数")
    icon: str = Field(description="图标名")
    source: str = Field(description="来源：builtin / custom")
    skill_id: int | None = Field(default=None, description="自定义技能的主键；内置为空")
    mounted: bool = Field(default=False, description="是否是当前会话挂载的技能")


class SkillDetail(SkillItem):
    instructions: str = Field(description="Markdown 正文")


class SkillListResponse(BaseModel):
    items: list[SkillItem] = Field(description="内置 + 自定义，内置在前")
    mounted: str | None = Field(default=None, description="当前会话挂载的技能 slug")


class SkillCreateRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=32, description="标识，小写字母数字与连字符")
    name: str = Field(min_length=1, max_length=30, description="展示名")
    description: str = Field(min_length=1, max_length=120, description="一句话说明")
    instructions: str = Field(min_length=1, max_length=4000, description="Markdown 正文")
    tools: list[str] = Field(default_factory=list, description="工具白名单，空表示不限制")
    icon: str = Field(default="sparkle", max_length=32, description="图标名")


class SkillUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=30)
    description: str | None = Field(default=None, min_length=1, max_length=120)
    instructions: str | None = Field(default=None, min_length=1, max_length=4000)
    tools: list[str] | None = Field(default=None)
    icon: str | None = Field(default=None, max_length=32)


class SkillMountRequest(BaseModel):
    slug: str | None = Field(default=None, description="要挂载的技能；null 表示卸载")
