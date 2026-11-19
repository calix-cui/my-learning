from pydantic import BaseModel, Field


class LocalSkillItem(BaseModel):
    key: str
    slug: str
    name: str
    description: str
    source: str
    trust: str
    version: str
    tools: list[str]
    icon: str


class SkillCatalogResponse(BaseModel):
    items: list[LocalSkillItem]
    version: str


class SkillMountRequest(BaseModel):
    slug: str | None = Field(default=None, description="要挂载的技能；null 表示卸载")
