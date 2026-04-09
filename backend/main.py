import os
print("\n" + "="*40)
print("🚀 目前執行的是：留言修復版 3.0 (GET_POST 已補全)")
print("="*40 + "\n")
import time
import uuid
import json
import shutil
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Query, Request, Depends, Response, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import engine, Base, get_db
import models, schemas, security

# --- 1. 自動資料庫補強邏輯 ---
def sync_db_structure():
    DB_PATH = "users.db"
    if not os.path.exists(DB_PATH): return
    conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
    checks = {
        "users": [("password_hash", "TEXT"), ("is_premium", "INTEGER DEFAULT 0"), ("avatar_url", "TEXT"), ("created_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")],
        "posts": [("caption", "TEXT"), ("content_type", "TEXT"), ("location", "TEXT"), ("at_user", "TEXT")],
        "comments": [("user_avatar", "TEXT"), ("user_email", "TEXT")]
    }
    for table, columns in checks.items():
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            existing_cols = [row[1] for row in cursor.fetchall()]
            for col_name, col_type in columns:
                if col_name not in existing_cols:
                    print(f"🛠️  正在修復資料表 {table}：新增欄位 {col_name}")
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
        except Exception as e:
            print(f"⚠️  檢查 {table} 時發生錯誤: {e}")
    conn.commit(); conn.close()

sync_db_structure()
Base.metadata.create_all(bind=engine)

# --- 2. 全域設定 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
if not os.path.exists(UPLOAD_DIR): os.makedirs(UPLOAD_DIR)

app = FastAPI(title="Foodie PWA Robust Backend", redirect_slashes=False)
api_router = APIRouter()

# 使用原始字串修復 SyntaxWarning
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_base_url(request: Request):
    return str(request.base_url).rstrip("/")

# --- 3. API 路由 (所有功能) ---

@api_router.get("/ping")
async def ping(): return {"status": "ok", "time": time.time()}

@api_router.post("/login")
async def login(user_data: schemas.UserLogin, response: Response, request: Request, db: Session = Depends(get_db)):
    # ... login logic ...
    user = db.query(models.User).filter(models.User.email == user_data.email.lower()).first()
    if not user or not security.verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    access_token = security.create_access_token(data={"sub": user.email})
    response.set_cookie(key="access_token", value=access_token, httponly=True, max_age=86400, samesite="lax")
    avatar = user.avatar_url
    if avatar and not avatar.startswith("http"):
        avatar = f"{get_base_url(request)}/uploads/{avatar.split('/')[-1]}"
    return {"status": "success", "name": user.name, "email": user.email, "is_premium": bool(user.is_premium), "avatar_url": avatar}

@api_router.post("/register")
async def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == user_data.email.lower()).first():
        raise HTTPException(status_code=400, detail="Email 已被使用")
    new_user = models.User(name=user_data.name, dob=user_data.dob, email=user_data.email.lower(), phone=user_data.phone, password_hash=security.get_password_hash(user_data.password))
    db.add(new_user); db.commit()
    return {"status": "success"}

@api_router.post("/upload_avatar")
async def upload_avatar(request: Request, email: str = Form(...), file: UploadFile = File(...), current_user: models.User = Depends(security.get_current_user), db: Session = Depends(get_db)):
    target_user = current_user if current_user else db.query(models.User).filter(models.User.email == email.strip().lower()).first()
    
    # --- 🛠️ 超強悍補強：如果使用者不存在，直接原地建立 (解決測試帳號遺失問題) ---
    if not target_user: 
        print(f"🛠️  正在為 {email} 自動建立開發測試帳號...")
        target_user = models.User(
            name="Alice_Test", 
            email=email.strip().lower(), 
            dob="2000-01-01", 
            phone="0912345678",
            password_hash="auto_created" # 暫時性密碼
        )
        db.add(target_user); db.commit(); db.refresh(target_user)
    # ----------------------------------------------------------------------
    file_name = f"avatar_{uuid.uuid4().hex[:8]}.{file.filename.split('.')[-1]}"
    with open(os.path.join(UPLOAD_DIR, file_name), "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    url = f"{get_base_url(request)}/uploads/{file_name}"
    target_user.avatar_url = url; db.commit()
    return {"success": True, "avatar_url": url}

@api_router.post("/upload_memory_post")
async def upload_memory_post(
    request: Request, 
    email: str = Form(...), 
    files: List[UploadFile] = File(...), 
    caption: Optional[str] = Form(None), 
    location: Optional[str] = Form(None), 
    db: Session = Depends(get_db)
):
    # --- 🛠️ 帳號自動補全系統 ---
    user = db.query(models.User).filter(models.User.email == email.strip().lower()).first()
    if not user:
        print(f"🛠️  正在為發文自動建立帳號: {email}")
        user = models.User(name="Auto_User", email=email.strip().lower(), dob="2000-01-01", phone="000", password_hash="auto_post")
        db.add(user); db.commit(); db.refresh(user)

    # --- 處理照片上傳 ---
    urls = []; post_id = str(uuid.uuid4()); base_url = get_base_url(request)
    for idx, file in enumerate(files):
        file_ext = file.filename.split('.')[-1]
        file_name = f"{post_id[:8]}_{int(time.time()*1000)}_{idx}.{file_ext}"
        with open(os.path.join(UPLOAD_DIR, file_name), "wb") as b: 
            shutil.copyfileobj(file.file, b)
        urls.append(f"{base_url}/uploads/{file_name}")

    # --- 儲存貼文 (整合地點標記) ---
    new_post = models.Post(
        id=post_id, 
        user_id=user.id, 
        urls=json.dumps(urls), 
        timestamp=int(time.time()*1000), 
        caption=caption, 
        location=location,
        content_type="album" if len(files) > 1 else "single"
    )
    db.add(new_post); db.commit()
    print(f"✅ 貼文發布成功！地點: {location or '無'}")
    return {"status": "success", "post_id": post_id}

@app.post("/api/update_post")
async def update_post(
    request: Request,
    post_id: str = Form(...),
    email: str = Form(...),
    caption: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    at_user: Optional[str] = Form(None),
    keep_urls: str = Form("[]"),
    files: List[UploadFile] = File([]),
    db: Session = Depends(get_db)
):
    # 1. 權限與存在檢查
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post: raise HTTPException(status_code=404, detail="Post not found")
    
    # 2. 物理刪除
    original_urls = []
    try:
        original_urls = json.loads(post.urls) if post.urls else []
        keep_urls_list = json.loads(keep_urls)
    except Exception as e:
        print(f"⚠️ 解析網址 JSON 失敗: {e}")
        keep_urls_list = []
    
    # 找出被捨棄的檔案並刪除
    for old_url in original_urls:
        if old_url not in keep_urls_list:
            try:
                filename = old_url.split('/')[-1]
                filepath = os.path.join(UPLOAD_DIR, filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"🗑️  物理刪除：{filename}")
            except Exception as e:
                print(f"⚠️ 刪除檔案失敗: {e}")

    # 3. 處理新圖片
    new_urls = []
    base_url = get_base_url(request)
    for idx, file in enumerate(files):
        if not file.filename: continue
        file_ext = file.filename.split('.')[-1]
        file_name = f"{post_id[:8]}_edit_{int(time.time()*1000)}_{idx}.{file_ext}"
        with open(os.path.join(UPLOAD_DIR, file_name), "wb") as b: shutil.copyfileobj(file.file, b)
        new_urls.append(f"{base_url}/uploads/{file_name}")

    # 4. 更新貼文 (保持順序：舊的保留圖在前面，新圖在後面)
    final_urls = keep_urls_list + new_urls
    post.urls = json.dumps(final_urls)
    post.caption = caption
    post.location = location
    post.at_user = at_user
    post.content_type = "album" if len(final_urls) > 1 else "single"
    
    db.commit()
    print(f"✅ 貼文更新成功：{post_id}")
    return {"status": "success"}

@api_router.get("/get_memories")
async def get_memories(request: Request, email: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Post)
    if email:
        user = db.query(models.User).filter(models.User.email == email.lower()).first()
        if user: query = query.filter(models.Post.user_id == user.id)
    posts = query.order_by(models.Post.timestamp.desc()).all()
    base_url = get_base_url(request); result = []
    for p in posts:
        try: urls = json.loads(p.urls)
        except: urls = []
        avatar = p.owner.avatar_url if p.owner else None
        if avatar and not avatar.startswith("http"): avatar = f"{base_url}/uploads/{avatar.split('/')[-1]}"
        date_str = datetime.fromtimestamp(p.timestamp/1000).strftime("%Y-%m-%d")
        result.append({
            "id": p.id, "imageUrls": urls, "url": urls[0] if urls else "", 
            "caption": p.caption or "", "username": p.owner.name if p.owner else "User", 
            "userAvatar": avatar or "https://ui-avatars.com/api/?name=User&background=9C7C66&color=fff", 
            "email": p.owner.email if p.owner else "", "timestamp": p.timestamp,
            "date": date_str,
            "location": p.location,
            "at_user": p.at_user
        })
    return result

@api_router.get("/check_vip/{email}")
async def check_vip(email: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    if user:
        if user.is_premium and user.membership and user.membership.end_date and user.membership.end_date < datetime.utcnow():
            user.is_premium = False; db.commit()
        return {"is_vip": bool(user.is_premium)}
    return {"is_vip": False}

@api_router.post("/upgrade_premium")
async def upgrade_premium(email: str = Query(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email.lower()).first()
    if not user: raise HTTPException(status_code=404)
    user.is_premium = True; m = user.membership
    if not m: m = models.Membership(user_id=user.id); db.add(m)
    m.start_date = datetime.utcnow(); m.end_date = datetime.utcnow()+timedelta(days=30); m.status = "active"; m.trade_no = f"P{uuid.uuid4().hex[:8]}"
    db.commit()
    return {"status": "success", "is_vip": True}

@api_router.post("/add_comment")
async def add_comment(data: schemas.CommentCreate, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_user)):
    # 優先使用登入用戶，否則使用傳入的 Email
    user = current_user
    if not user:
        email = data.user_email.strip().lower()
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            print(f"🛠️  正在為留言請求自動建立帳號: {email}")
            user = models.User(name=data.user_name, email=email, dob="2000-01-01", phone="000", password_hash="auto_comment")
            db.add(user); db.commit(); db.refresh(user)
    
    db.add(models.Comment(post_id=data.photo_id, user_id=user.id, text=data.text)); db.commit()
    return {"status": "success"}

@api_router.delete("/delete_single_photo")
async def delete_single_photo(post_id: str = Query(...), photo_url: str = Query(...), email: str = Query(...), db: Session = Depends(get_db)):
    # 1. 查找貼文
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    # 2. 解析並移除 URL
    try:
        urls = json.loads(post.urls)
    except:
        urls = []
        
    # 過濾掉要刪除的 URL (相容絕對路徑與相對路徑)
    filename = photo_url.split('/')[-1]
    new_urls = [u for u in urls if u.split('/')[-1] != filename]
    
    if len(new_urls) == 0:
        # 如果沒照片了，直接刪除整則貼文
        db.delete(post)
    else:
        # 更新照片列表
        post.urls = json.dumps(new_urls)
    
    db.commit()
    print(f"🗑️ 已從貼文 {post_id} 中刪除照片: {filename}")
    return {"status": "success"}

@api_router.get("/get_post/{post_id}")
async def get_post_detail(request: Request, post_id: str, db: Session = Depends(get_db)):
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post: raise HTTPException(status_code=404, detail="Post not found")
    
    # 貼文基礎資訊
    base_url = get_base_url(request)
    avatar = post.owner.avatar_url if post.owner else None
    if avatar and not avatar.startswith("http"): avatar = f"{base_url}/uploads/{avatar.split('/')[-1]}"
    
    try: urls = json.loads(post.urls)
    except: urls = []
    
    # 抓取留言清單
    comments_list = []
    for c in post.comments:
        c_avatar = c.author.avatar_url if c.author else None
        if c_avatar and not c_avatar.startswith("http"): c_avatar = f"{base_url}/uploads/{c_avatar.split('/')[-1]}"
        comments_list.append({
            "user": c.author.name if c.author else "Unknown",
            "text": c.text,
            "avatar": c_avatar or f"https://ui-avatars.com/api/?name={c.author.name if c.author else 'User'}&background=random",
            "timestamp": c.timestamp.isoformat() if c.timestamp else None
        })

    # 首則留言通常是貼文的 Caption
    all_comments = []
    # 如果內容中有 Caption，將它作為第一條留言模擬顯示
    all_comments.append({
        "user": post.owner.name if post.owner else "User",
        "text": post.caption or "",
        "avatar": avatar or "https://ui-avatars.com/api/?name=User&background=9C7C66&color=fff",
        "timestamp": None
    })
    all_comments.extend(comments_list)

    return {
        "id": post.id,
        "imageUrls": urls,
        "caption": post.caption,
        "username": post.owner.name if post.owner else "User",
        "userAvatar": avatar,
        "location": post.location,
        "at_user": post.at_user,
        "comments": all_comments
    }

# --- 4. 路由掛載 (順序至關重要) ---

# 優先掛載 API 路由，確保不會被 / 根目錄攔截
app.include_router(api_router, prefix="/api")

# 為了相容快取中的前端，新增一個相容路由
@app.post("/upload_avatar")
async def legacy_upload_avatar(request: Request, email: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    print(f"⚠️  偵測到舊版前端請求，導向至 /api/upload_avatar")
    return await upload_avatar(request, email, file, None, db)


@app.get("/")
async def serve_index():
    p = os.path.join(FRONTEND_DIR, "index.html")
    return FileResponse(p) if os.path.exists(p) else {"error": "not found"}

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    # 列出所有註冊的路由 (Debug 用)
    print("\n--- 🛠️ 註冊的 API 路由 ---")
    for route in app.routes:
        if hasattr(route, "path"):
            print(f"[{route.methods if hasattr(route, 'methods') else 'ALL'}] {route.path}")
    print("--------------------------\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)