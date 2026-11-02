from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi import FastAPI, HTTPException, Path, Query
from enum import Enum
from pydantic import BaseModel, Field


class ModelProductsType(str, Enum):
    foods = "foods"
    toys = "toys"
    clothes = "clothes"


class ProductCreate(BaseModel):
    """描述新增商品时，客户端可以提交的字段"""

    name: str = Field(min_length=1, max_length=50, description="商品名称，必填")
    price: Decimal = Field(
        ge=0, decimal_places=2, max_digits=8, description="商品价格，保留2位小数"
    )
    category_id: int = Field(gt=0, description="商品分类的 id，必须是正整数")
    stock: int = Field(ge=0, description="库存，不小于 0")
    shelf_status: bool = Field(default=False, description="上架状态")


class ProductUpdate(BaseModel):
    """局部修改字段"""

    name: str | None = Field(
        default=None, min_length=1, max_length=50, description="商品名称，必填"
    )
    price: Decimal | None = Field(
        default=None,
        ge=0,
        decimal_places=2,
        max_digits=8,
        description="商品价格，保留2位小数",
    )
    category_id: int | None = Field(
        default=None, gt=0, description="商品分类的 id，必须是正整数"
    )
    stock: int | None = Field(default=None, ge=0, description="库存，不小于 0")
    shelf_status: bool | None = Field(default=None, description="上架状态")


app = FastAPI()

# @app.get('/')
# def root():
#     return {"message": "FastAPI Service is Running"}

categories = [
    {"id": 1, "name": "饮料", "create_time": "2026-10-13 08:00:00"},
    {"id": 2, "name": "数码配件", "create_time": "2026-10-13 08:00:00"},
    {"id": 3, "name": "零食", "create_time": "2026-10-13 08:00:00"},
]


def get_categories_id():
    return [item["id"] for item in categories]


products = [
    {
        "id": 1,
        "category_id": 1,
        "name": "矿泉水",
        "price": 3.50,
        "stock": 100,
        "shelf_status": True,
        "create_time": "2026-10-13 09:00:00",
    },
    {
        "id": 2,
        "category_id": 1,
        "name": "可乐",
        "price": 5.00,
        "stock": 80,
        "shelf_status": True,
        "create_time": "2026-10-13 10:00:00",
    },
    {
        "id": 3,
        "category_id": 2,
        "name": "USB 数据线",
        "price": 19.90,
        "stock": 0,
        "shelf_status": False,
        "create_time": "2026-10-13 11:00:00",
    },
]


@app.get("/products/count")
def get_products_count():
    return {"count": len(products)}


def get_product_by_id(product_id):
    # 根据 id 查询产品的方法，返回产品或者 404
    product = next((item for item in products if item["id"] == product_id), None)
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product


@app.get("/products/{product_id}")
def search_product(product_id: int = Path(gt=0)):
    """接收商品ID，返回匹配的商品"""
    return get_product_by_id(product_id)


@app.get("/products")
def list_products(
    keywords: str | None = Query(default=None, max_length=50, description="关键字查询"),
    page: int = Query(default=1, ge=1, description="页码，默认为第一页"),
    pageSize: int = Query(
        default=2, ge=1, le=100, description="每页数量，默认为每页 2 条显示"
    ),
):
    """接收页码和每页条数，返回当前页的商品和商品总数"""
    filter_products = products
    print(keywords)
    if keywords and keywords.strip():
        search_text = keywords.strip().lower()
        filter_products = []
        for product in products:
            if search_text in product["name"].lower():
                filter_products.append(product)

    start = (page - 1) * pageSize
    end = page * pageSize
    return {
        "items": filter_products[start:end],
        "total": len(filter_products),
        "page": page,
        "pageSize": pageSize,
    }


def validateFields(payload: ProductCreate | ProductUpdate):
    """校验 Product 各个字段有效性"""
    payload_dict = payload.model_dump(exclude_none=True)
    # 检验name
    if "name" in payload_dict and not payload_dict["name"].strip():
        raise HTTPException(status_code=400, detail="商品名称不能为空")

    # 校验有效分类
    if "category_id" in payload_dict and not any(
        payload_dict["category_id"] == category["id"] for category in categories
    ):
        raise HTTPException(status_code=400, detail="分类ID不存在")


@app.post("/products")
def create_product(payload: ProductCreate):
    """接收商品新增的数据，暂时先返回校验后数据"""
    validateFields(payload)

    name = payload.name.strip()
    payload.name = name

    # 新增商品 从商品列表找出最大的 ID，再 +1 变成新的商品 ID
    next_id = max((product["id"] for product in products), default=0) + 1
    product = {
        **payload.model_dump(),
        "id": next_id,
        "create_time": datetime.now(timezone(timedelta(hours=8))).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    }  # UTC +8
    products.append(product)
    return products


# 更新某商品
@app.patch("/products/{product_id}")
def update_product(product_id: int, payload: ProductUpdate):
    """更新商品数据"""
    # 校验
    changes = payload.model_dump(exclude_unset=True)
    if not changes:  # {}
        raise HTTPException(status_code=400, detail="参数不合法")
    ori_product = get_product_by_id(product_id)
    validateFields(payload)
    for field, value in changes.items():
        if value is None:
            # 判断 None 值字段
            raise HTTPException(
                status_code=400, detail=f"字段 {field} 的值不允许为 null"
            )

    # print(changes)
    ori_product.update(changes)
    # print(ori_product)
    return ori_product

# 删除商品
@app.delete("/products/{product_id}")
def delete_product(product_id: int):
    """根据商品 ID 删除商品"""
    product = get_product_by_id(product_id)
    products.remove(product)
    return {"message": "商品删除成功"}

# 添加数据
@app.post("/products/add")
def add_product(data: ProductCreate):
    """添加商品"""

    return None
