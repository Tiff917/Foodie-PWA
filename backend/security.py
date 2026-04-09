import os
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.orm import Session
from database import get_db
import models

# 配置加密設定
SECRET_KEY = os.getenv("SECRET_KEY", "morandi_palette_secret_key_123456")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 小時

def verify_password(plain_password: str, hashed_password: str):
    """驗證密碼，解決 passlib 與新版 bcrypt 的相容性問題"""
    try:
        # bcrypt 要求 bytes
        password_bytes = plain_password.encode('utf-8')
        # bcrypt 的密碼長度上限為 72 bytes，若超過會出錯，這裡進行截斷以確保穩固
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
            
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False

def get_password_hash(password: str):
    """產生密碼雜湊，直接使用 bcrypt 避免依賴 passlib"""
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
        
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    """
    從 Cookie 或 Header 取得使用者 (優先支援 Cookie 以符合「不動前端」需求)
    """
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    
    if not token:
        return None 

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception
    
    # 付費會員診斷邏輯
    if user.is_premium and user.membership:
        if user.membership.end_date and user.membership.end_date < datetime.utcnow():
            user.is_premium = False
            user.membership.status = "expired"
            db.commit()
            
    return user
