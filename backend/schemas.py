from pydantic import BaseModel, EmailStr, ConfigDict
from typing import List, Optional
from datetime import datetime

class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone: str
    dob: str

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    email: str
    name: str
    is_premium: bool
    avatar_url: Optional[str] = None

class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    urls: List[str]
    timestamp: int
    caption: str
    content_type: str
    username: str
    userAvatar: Optional[str] = None
    email: str

class CommentCreate(BaseModel):
    photo_id: str
    user_email: str
    user_name: str
    text: str

class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    user: str
    text: str
    avatar: Optional[str] = None
    timestamp: datetime
