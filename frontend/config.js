// --- 1. 全域配置 ---
const DB_CONFIG = {
    name: "MemoriesDB",
    version: 18, // 統一版本號
    apiUrl: (window.location.origin.includes(':') 
            ? (window.location.origin.includes(':5000') ? window.location.origin.replace(':5000', ':8000') : window.location.origin)
            : "http://127.0.0.1:8000") + "/api"
};

// --- 2. 通用資料庫初始化 (整合自 db.js) ---
function initDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_CONFIG.name, DB_CONFIG.version);

        request.onupgradeneeded = (e) => {
            const db = e.target.result;
            // 建立日曆回憶存儲
            if (!db.objectStoreNames.contains("all_photos")) {
                db.createObjectStore("all_photos", { autoIncrement: true });
            }
            // 建立社群貼文存儲
            if (!db.objectStoreNames.contains("posts_timeline")) {
                db.createObjectStore("posts_timeline", { keyPath: "id" });
            }
            // 建立用戶資料存儲
            if (!db.objectStoreNames.contains("user_profile")) {
                db.createObjectStore("user_profile");
            }
        };

        request.onsuccess = (e) => resolve(e.target.result);
        request.onerror = (e) => {
            console.error("IndexedDB 開啟失敗:", e.target.error);
            reject("資料庫開啟失敗");
        };
    });
}

// --- 3. 通用用戶資料儲存工具 ---
async function saveUserData(name, avatarBlob) {
    try {
        const db = await initDB();
        const tx = db.transaction("user_profile", "readwrite");
        const store = tx.objectStore("user_profile");

        if (name) store.put(name, "username");
        if (avatarBlob) store.put(avatarBlob, "avatar");

        return new Promise((resolve) => {
            tx.oncomplete = () => {
                console.log("✅ 用戶資料已更新於 IndexedDB");
                // 通知其他頁面 (如 Social 頁面) 同步頭像與名字
                new BroadcastChannel('memory_update').postMessage('user_updated');
                resolve(true);
            };
        });
    } catch (err) {
        console.error("儲存用戶資料失敗:", err);
        return false;
    }
}