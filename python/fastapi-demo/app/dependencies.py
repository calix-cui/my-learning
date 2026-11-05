from app.database import SessionLocal


def get_db():
    """为一次性请求提供 session 使用后关闭"""
    with SessionLocal() as db:
        yield db
