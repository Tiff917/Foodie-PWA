import time
from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, BigInteger, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    dob = Column(String)
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    password_hash = Column(String) # 改用雜湊儲存
    is_premium = Column(Boolean, default=False)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 關聯
    posts = relationship("Post", back_populates="owner")
    membership = relationship("Membership", back_populates="user", uselist=False)

class Membership(Base):
    __tablename__ = "memberships"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    trade_no = Column(String, unique=True) # 綠界交易編號
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True)) # 到期時間
    status = Column(String, default="active")

    user = relationship("User", back_populates="membership")

class Post(Base):
    __tablename__ = "posts"

    id = Column(String, primary_key=True, index=True) # 使用 UUID
    user_id = Column(Integer, ForeignKey("users.id"))
    urls = Column(Text) # JSON string of image URLs
    timestamp = Column(BigInteger) # 毫秒級時間戳
    caption = Column(Text, nullable=True)
    location = Column(String, nullable=True) # 地點標記
    at_user = Column(Text, nullable=True)   # 標註的朋友
    content_type = Column(String) # 'single', 'album'

    owner = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(String, ForeignKey("posts.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    text = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    post = relationship("Post", back_populates="comments")
    author = relationship("User")
