# checkin/firebase_init.py

import os
import json
from django.conf import settings
from firebase_admin import credentials, initialize_app, firestore
from pathlib import Path
from firebase_admin import _apps as initialized_apps  # 導入已初始化 app 檢查

# 讓 client 保持在模組級別，避免重複初始化
_firestore_client = None


def get_firestore_client():
    """
    初始化並返回單例 (Singleton) Firestore Client。
    """
    global _firestore_client

    if _firestore_client is not None:
        return _firestore_client

    FIREBASE_CREDENTIALS = None

    # --- 獲取認證資料 ---
    FIREBASE_CREDENTIALS_JSON = os.environ.get('FIREBASE_CREDENTIALS_JSON')

    if FIREBASE_CREDENTIALS_JSON:
        # 方式一：從環境變數載入 (Render)
        try:
            FIREBASE_CREDENTIALS = json.loads(FIREBASE_CREDENTIALS_JSON)
        except json.JSONDecodeError:
            print("FIREBASE_CREDENTIALS_JSON 環境變數 JSON 解析錯誤！")
            return None
    else:
        # 方式二：從檔案載入 (本地開發)
        try:
            # 假設 settings.BASE_DIR 已經設定好，指向專案根目錄
            BASE_DIR = settings.BASE_DIR
            # 使用 resolve() 確保路徑是絕對的
            key_path = BASE_DIR / "serviceAccountKey.json"
            with open(key_path.resolve(), "r") as f:
                FIREBASE_CREDENTIALS = json.load(f)

        # 捕獲所有可能的本地錯誤
        except FileNotFoundError:
            print(f"本地未找到 serviceAccountKey.json 檔案。預期路徑: {key_path}")
        except AttributeError:
            print("settings.BASE_DIR 存取錯誤，請確認 settings.py 設定。")
        except Exception as e:
            # 捕獲其他如 JSON 格式錯誤
            print(f"載入 serviceAccountKey.json 時發生錯誤: {e}")

    # --- 執行初始化 ---
    if FIREBASE_CREDENTIALS:
        try:
            # 檢查是否已經有預設 App 初始化，避免重複初始化錯誤
            if not initialized_apps:
                cred = credentials.Certificate(FIREBASE_CREDENTIALS)
                initialize_app(cred)
                print("Firebase Admin SDK 初始化成功！")

            # 獲取 Firestore 客戶端
            _firestore_client = firestore.client()
            return _firestore_client

        except Exception as e:
            # 捕獲所有初始化錯誤，例如認證失敗
            print(f"Firebase 初始化失敗: 請檢查金鑰內容或網路連線。錯誤: {e}")
            return None

    # 如果 FIREBASE_CREDENTIALS 是 None，則表示認證資訊缺失
    print("警告: 未找到 Firebase 認證資訊，Firebase 功能將無法使用。")
    return None