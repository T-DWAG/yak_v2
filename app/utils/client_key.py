import json
import time
import hashlib
import platform
import uuid
from typing import Dict
from .license_manager import license_manager


def get_machine_fingerprint() -> str:
    """获取简单的机器指纹（不包含敏感硬件信息）"""
    # 使用系统信息生成简单指纹
    system_info = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "node": uuid.getnode()
    }

    fingerprint_data = json.dumps(system_info, sort_keys=True)
    fingerprint = hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]

    return fingerprint


def generate_client_key() -> Dict:
    """生成客户端钥匙"""
    if not license_manager.can_generate_client_key():
        raise ValueError("暂无处理记录，无法生成客户端钥匙")

    # 获取使用统计
    usage_stats = license_manager.get_usage_stats()
    is_valid, _, license_data = license_manager.validate_current_license()

    # 构建客户端钥匙数据
    client_key = {
        "type": "client_usage_key",
        "version": "1.0",
        "generated_at": int(time.time()),
        "machine_fingerprint": get_machine_fingerprint(),
        "usage_statistics": {
            "total_images_processed": usage_stats.get("total_images_processed", 0),
            "total_sessions": usage_stats.get("total_sessions", 0),
            "last_usage_time": usage_stats.get("last_usage_time"),
            "current_session_images": usage_stats.get("current_session_images", 0)
        },
        "license_info": {
            "license_id": license_data.get("license_id") if license_data else None,
            "images_used": usage_stats.get("total_images_processed", 0),
            "images_remaining": license_data.get("total_images_allowed", 0) - usage_stats.get("total_images_processed", 0) if license_data else 0
        },
        "client_info": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "product": "牦牛图片跨案件号相似度分析系统"
        }
    }

    return client_key


def validate_client_key_for_license_generation(client_key_data: Dict) -> tuple[bool, str]:
    """验证客户端钥匙是否可用于生成授权文件"""
    try:
        # 检查基本结构
        required_fields = ["type", "version", "generated_at", "usage_statistics", "machine_fingerprint"]
        for field in required_fields:
            if field not in client_key_data:
                return False, f"客户端钥匙缺少必要字段: {field}"

        # 检查类型
        if client_key_data.get("type") != "client_usage_key":
            return False, "客户端钥匙类型无效"

        # 检查使用统计
        usage_stats = client_key_data.get("usage_statistics", {})
        if usage_stats.get("total_images_processed", 0) <= 0:
            return False, "客户端钥匙无处理记录"

        # 检查生成时间（不能是未来时间，也不能太久远）
        generated_at = client_key_data.get("generated_at", 0)
        current_time = int(time.time())
        if generated_at > current_time:
            return False, "客户端钥匙生成时间无效"

        # 检查钥匙年龄（不超过30天）
        max_age = 30 * 24 * 60 * 60  # 30天
        if current_time - generated_at > max_age:
            return False, "客户端钥匙已过期（超过30天）"

        return True, "客户端钥匙有效"

    except Exception as e:
        return False, f"验证客户端钥匙失败: {str(e)}"


def extract_usage_info_from_client_key(client_key_data: Dict) -> Dict:
    """从客户端钥匙提取使用信息（用于授权生成）"""
    usage_stats = client_key_data.get("usage_statistics", {})
    client_info = client_key_data.get("client_info", {})

    return {
        "current_usage": {
            "total_images_processed": usage_stats.get("total_images_processed", 0),
            "total_sessions": usage_stats.get("total_sessions", 0),
            "last_usage_time": usage_stats.get("last_usage_time")
        },
        "client_info": {
            "platform": client_info.get("platform"),
            "python_version": client_info.get("python_version"),
            "machine_fingerprint": client_key_data.get("machine_fingerprint")
        },
        "key_generated_at": client_key_data.get("generated_at"),
        "original_license_id": client_key_data.get("license_info", {}).get("license_id")
    }


def save_client_key_to_file(client_key_data: Dict, file_path: str) -> bool:
    """保存客户端钥匙到文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(client_key_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存客户端钥匙失败: {str(e)}")
        return False


def load_client_key_from_file(file_path: str) -> Dict:
    """从文件加载客户端钥匙"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载客户端钥匙失败: {str(e)}")
        return {}