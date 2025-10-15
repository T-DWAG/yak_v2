import os
import json
import sqlite3
import time
from typing import Dict, Optional, Tuple
from .crypto_utils import encrypt_license_data, decrypt_license_data, validate_license


class LicenseManager:
    def __init__(self, license_file_path: str = "license_data/license.json"):
        self.license_file_path = license_file_path
        self.usage_file_path = "license_data/usage.json"
        self.db_path = "license_data/license.db"
        self._ensure_dirs()
        self._init_db()

    def _ensure_dirs(self):
        """确保目录存在"""
        os.makedirs(os.path.dirname(self.license_file_path), exist_ok=True)

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS license_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE,
            start_time INTEGER,
            images_processed INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active'
        )
        """)

        conn.commit()
        conn.close()

    def load_license(self) -> Optional[Dict]:
        """加载授权文件"""
        if not os.path.exists(self.license_file_path):
            return None

        try:
            with open(self.license_file_path, 'r', encoding='utf-8') as f:
                license_file = json.load(f)

            # 解密授权数据
            license_data = decrypt_license_data(license_file)
            return license_data

        except Exception as e:
            print(f"加载授权文件失败: {str(e)}")
            return None

    def save_license(self, license_file: Dict) -> bool:
        """保存授权文件"""
        try:
            with open(self.license_file_path, 'w', encoding='utf-8') as f:
                json.dump(license_file, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存授权文件失败: {str(e)}")
            return False

    def validate_current_license(self) -> Tuple[bool, str, Optional[Dict]]:
        """验证当前授权"""
        license_data = self.load_license()
        if license_data is None:
            return False, "未找到授权文件", None

        is_valid, message = validate_license(license_data)
        if not is_valid:
            return False, message, license_data

        return True, "授权有效", license_data

    def get_usage_stats(self) -> Dict:
        """获取使用统计"""
        default_stats = {
            "total_images_processed": 0,
            "total_sessions": 0,
            "current_session_images": 0,
            "last_usage_time": None
        }

        if os.path.exists(self.usage_file_path):
            try:
                with open(self.usage_file_path, 'r', encoding='utf-8') as f:
                    stats = json.load(f)
                default_stats.update(stats)
            except Exception:
                pass

        return default_stats

    def save_usage_stats(self, stats: Dict) -> bool:
        """保存使用统计"""
        try:
            with open(self.usage_file_path, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存使用统计失败: {str(e)}")
            return False

    def get_license_status(self) -> Dict:
        """获取授权状态信息"""
        is_valid, message, license_data = self.validate_current_license()
        usage_stats = self.get_usage_stats()

        if not is_valid:
            return {
                "authorization_status": "unauthorized",
                "authorization_message": message,
                "images_used": 0,
                "total_images_allowed": 0,
                "images_remaining": 0,
                "sessions_used": usage_stats.get("total_sessions", 0),
                "max_sessions": 0,
                "valid_until": None,
                "license_id": None
            }

        total_allowed = license_data["total_images_allowed"]
        used = usage_stats.get("total_images_processed", 0)
        remaining = max(0, total_allowed - used)

        return {
            "authorization_status": "authorized",
            "authorization_message": "授权有效",
            "images_used": used,
            "total_images_allowed": total_allowed,
            "images_remaining": remaining,
            "sessions_used": usage_stats.get("total_sessions", 0),
            "max_sessions": license_data["max_sessions"],
            "valid_until": time.strftime("%Y-%m-%d %H:%M:%S",
                                       time.localtime(license_data["expires_at"])),
            "license_id": license_data["license_id"]
        }

    def check_processing_permission(self, estimated_images: int = 0) -> Tuple[bool, str]:
        """检查是否允许处理图片"""
        is_valid, message, license_data = self.validate_current_license()
        if not is_valid:
            return False, f"授权无效: {message}"

        usage_stats = self.get_usage_stats()
        total_allowed = license_data["total_images_allowed"]
        used = usage_stats.get("total_images_processed", 0)

        # 检查图片数量限制
        if used + estimated_images > total_allowed:
            remaining = total_allowed - used
            return False, f"许可量不足。剩余许可量: {remaining} 张，预计需要: {estimated_images} 张"

        # 检查会话次数限制
        sessions_used = usage_stats.get("total_sessions", 0)
        max_sessions = license_data["max_sessions"]
        if sessions_used >= max_sessions:
            return False, f"会话次数已达上限 ({max_sessions} 次)"

        return True, "可以处理"

    def start_processing_session(self) -> str:
        """开始新的处理会话"""
        import uuid

        session_id = str(uuid.uuid4())
        start_time = int(time.time())

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
            INSERT INTO license_sessions (session_id, start_time, images_processed, status)
            VALUES (?, ?, ?, ?)
            """, (session_id, start_time, 0, 'active'))

            conn.commit()
            return session_id
        except Exception as e:
            print(f"创建会话失败: {str(e)}")
            return ""
        finally:
            conn.close()

    def end_processing_session(self, session_id: str, images_processed: int):
        """结束处理会话"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
            UPDATE license_sessions
            SET images_processed = ?, status = 'completed'
            WHERE session_id = ?
            """, (images_processed, session_id))

            conn.commit()

            # 更新使用统计
            self._update_usage_stats(images_processed)

        except Exception as e:
            print(f"结束会话失败: {str(e)}")
        finally:
            conn.close()

    def _update_usage_stats(self, additional_images: int):
        """更新使用统计"""
        stats = self.get_usage_stats()
        stats["total_images_processed"] += additional_images
        stats["total_sessions"] += 1
        stats["last_usage_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        stats["current_session_images"] = additional_images

        self.save_usage_stats(stats)

    def can_generate_client_key(self) -> bool:
        """检查是否可以生成客户端钥匙"""
        usage_stats = self.get_usage_stats()
        return usage_stats.get("total_images_processed", 0) > 0

    def generate_client_key_data(self) -> Dict:
        """生成客户端钥匙数据"""
        usage_stats = self.get_usage_stats()
        is_valid, _, license_data = self.validate_current_license()

        return {
            "type": "client_usage_key",
            "generated_at": int(time.time()),
            "usage": usage_stats,
            "license_id": license_data.get("license_id") if license_data else None,
            "machine_id": "client_machine"  # 简化版本，不包含硬件信息
        }


# 全局实例
license_manager = LicenseManager()