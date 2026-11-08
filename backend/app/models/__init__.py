"""模型包对外入口：在这里汇总导出，其他层统一 `from app.models import Conversation`。

商品 / 分类模型已随商品管理模块一起归档，见 archive/product-admin/backend/app/models/。

显式声明 __all__ 有两个作用：
1. 让 lint 知道这些名字是“故意再导出”的，而不是未使用的导入；
2. 明确本包对外的公开接口。
"""

from app.models.conversation import Conversation
from app.models.message import Message

__all__ = ["Conversation", "Message"]
