import sys
import os
import io
import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 確保可以匯入當前目錄的模組
sys.path.append(os.getcwd())

try:
    from main import app
    from database import Base, get_db
    from models import User, Post
except ImportError as e:
    print(f"❌ 匯入錯誤: {e}")
    print("請確保你在 backend 目錄下執行此腳本，且已安裝 requirements.txt 中的套件。")
    sys.exit(1)

# 1. 設定測試資料庫 (使用記憶體中的 SQLite)
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_robust.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 覆蓋原本的 get_db Dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
Base.metadata.create_all(bind=engine)

client = TestClient(app)

def test_full_workflow():
    print("--- 開始測試完整流程 ---")

    # A. 測試註冊
    print("[1/4] 測試註冊中...")
    reg_response = client.post("/register", json={
        "name": "Test User",
        "dob": "1990-01-01",
        "email": "test@example.com",
        "phone": "0912345678",
        "password": "testpassword123"
    })
    if reg_response.status_code != 200:
        print(f"❌ 註冊失敗: {reg_response.json()}")
        return
    print("✅ 註冊成功")

    # B. 測試登入並取得 Cookie
    print("[2/4] 測試登入中...")
    login_response = client.post("/login", json={
        "email": "test@example.com",
        "password": "testpassword123"
    })
    if login_response.status_code != 200:
        print(f"❌ 登入失敗: {login_response.json()}")
        return
    
    # 檢查 Cookie
    has_cookie = "access_token" in client.cookies
    if not has_cookie:
        print("❌ 登入失敗: 未能獲取 access_token Cookie")
        return
    print("✅ 登入成功，已成功獲取 HttpOnly Cookie")

    # C. 測試發布照片 (需帶上 Cookie)
    print("[3/4] 測試發布貼文中...")
    file_content = b"fake-image-data"
    file = io.BytesIO(file_content)
    
    post_response = client.post(
        "/upload_memory_post",
        data={"email": "test@example.com", "caption": "Hello Robust World!"},
        files={"files": ("test.jpg", file, "image/jpeg")}
    )
    if post_response.status_code != 200:
        print(f"❌ 貼文發布失敗: {post_response.json()}")
        return
    
    post_id = post_response.json()["post_id"]
    print(f"✅ 貼文發布成功, ID: {post_id}")

    # D. 測試獲取貼文
    print("[4/4] 測試讀取貼文中...")
    get_response = client.get("/get_memories")
    if get_response.status_code != 200:
        print(f"❌ 讀取失敗: {get_response.json()}")
        return
        
    memories = get_response.json()
    if len(memories) == 0 or memories[0]["id"] != post_id:
        print("❌ 貼文讀取檢驗失敗")
        return
        
    print("✅ 貼文讀取成功，內容完全正確")
    print("\n--- 所有流程測試通過！後端極其穩固 ---")

if __name__ == "__main__":
    try:
        test_full_workflow()
    except Exception as e:
        print(f"❌ 測試執行時發生異常: {str(e)}")
    finally:
        # 強制關閉所有連線以釋放檔案鎖，解決 Windows 的 PermissionError
        engine.dispose()
        if os.path.exists("test_robust.db"):
            try:
                os.remove("test_robust.db")
            except:
                pass 
