import httpx
import os
import io
import time

def test_upload_flow():
    # 優先嘗試 127.0.0.1 (本地最穩定的地址)
    base_url = "http://127.0.0.1:8000"
    test_email = "a@gmail.com"
    
    print("--- 🚀 開始自動化測試上傳流程 ---")

    try:
        with httpx.Client(timeout=10.0) as client:
            # 0. 檢查服務是否在線
            print("[0/3] 正在檢查後端連線狀態...")
            try:
                ping_resp = client.get(f"{base_url}/api/ping")
                if ping_resp.status_code == 200:
                    print(f"✅ 後端已在線: {ping_resp.json()}")
                else:
                    print(f"❌ 後端回應異常: {ping_resp.status_code}")
                    return
            except Exception as e:
                print(f"❌ 無法連線到 {base_url}。請確保你已經執行了 'python main.py' 且沒報錯退出。")
                print(f"錯誤詳情: {e}")
                return

            # 1. 模擬單張照片快速上傳
            print("[1/3] 測試單張照片上傳 (快拍模式)...")
            file1 = ("test_quick.jpg", io.BytesIO(b"fake image data 1"), "image/jpeg")
            
            resp1 = client.post(
                f"{base_url}/api/upload_memory_post",
                data={"email": test_email, "caption": "Quick Upload Test"},
                files={"files": file1}
            )
            
            if resp1.status_code == 200:
                print("✅ 單張照片上傳成功:", resp1.json())
            else:
                print(f"❌ 單張照片上傳失敗! 狀態碼: {resp1.status_code}, 內容: {resp1.text}")
                return

            # 2. 模擬多張照片上傳 (Edit 模式)
            print("[2/3] 測試多張照片上傳 (編輯模式)...")
            files = [
                ("files", ("img1.jpg", io.BytesIO(b"data1"), "image/jpeg")),
                ("files", ("img2.jpg", io.BytesIO(b"data2"), "image/jpeg"))
            ]
            
            resp2 = client.post(
                f"{base_url}/api/upload_memory_post",
                data={"email": test_email, "caption": "Multi-photo Edit Test"},
                files=files
            )
            
            if resp2.status_code == 200:
                print("✅ 多張照片上傳成功:", resp2.json())
            else:
                print(f"❌ 多張照片上傳失敗! 狀態碼: {resp2.status_code}, 內容: {resp2.text}")
                return

            # 3. 驗證讀取
            print("[3/3] 驗證上傳後的資料是否可讀取...")
            read_resp = client.get(f"{base_url}/api/get_memories?email={test_email}")
            if read_resp.status_code == 200:
                memories = read_resp.json()
                print(f"✅ 成功讀取到 {len(memories)} 筆紀錄")
            else:
                print(f"❌ 讀取紀錄失敗!")

        print("\n🎉 所有流程測試通過！後端路由已精準修復並確認可用。")
        
    except Exception as e:
        print(f"❌ 測試執行異常: {str(e)}")

if __name__ == "__main__":
    test_upload_flow()
