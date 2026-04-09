import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 預設使用 SQLite，但保留切換到 PostgreSQL 的彈性
# 若偵測到 DATABASE_URL 環境變數則自動切換
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./users.db")

# 如果是 SQLite，需要設定 check_same_thread=False
connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """取得資料庫連線的 Dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
