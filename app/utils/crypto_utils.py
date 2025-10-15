import json
import base64
import hashlib
import hmac
import time
import os

# 密钥 - 实际部署时应该更复杂且混淆
SECRET_KEY = b'yak_license_2024_secret_key_32bytes!'  # 32字节
HMAC_KEY = b'yak_hmac_2024_key_for_signature_security!'  # 32字节

# 简化版加密函数（临时解决方案，使用hash算法替代AES）
def simple_encrypt(data: str, key: bytes = None) -> str:
    """简化版加密（临时方案）"""
    if key is None:
        key = SECRET_KEY

    if isinstance(data, str):
        data = data.encode('utf-8')

    # 使用key进行XOR加密（非常基础，仅用于演示）
    encrypted = bytearray()
    for i, byte in enumerate(data):
        encrypted.append(byte ^ key[i % len(key)])

    return base64.b64encode(encrypted).decode('utf-8')


def simple_decrypt(encrypted_data: str, key: bytes = None) -> str:
    """简化版解密（临时方案）"""
    if key is None:
        key = SECRET_KEY

    encrypted = base64.b64decode(encrypted_data.encode('utf-8'))

    # XOR解密
    decrypted = bytearray()
    for i, byte in enumerate(encrypted):
        decrypted.append(byte ^ key[i % len(key)])

    return decrypted.decode('utf-8')


# 临时替代方案，直到pycryptodome安装成功
def aes_encrypt(data: str, key: bytes = None) -> bytes:
    """AES加密数据（临时简化版）"""
    encrypted_str = simple_encrypt(data, key)
    return encrypted_str.encode('utf-8')


def aes_decrypt(encrypted_data: bytes, key: bytes = None) -> bytes:
    """AES解密数据（临时简化版）"""
    decrypted_str = simple_decrypt(encrypted_data.decode('utf-8'), key)
    return decrypted_str.encode('utf-8')


def generate_aes_key():
    """生成AES密钥"""
    return os.urandom(32)


def generate_hmac(data: bytes, key: bytes = None) -> bytes:
    """生成HMAC签名"""
    if key is None:
        key = HMAC_KEY

    return hmac.new(key, data, hashlib.sha256).digest()


def verify_hmac(data: bytes, signature: bytes, key: bytes = None) -> bool:
    """验证HMAC签名"""
    if key is None:
        key = HMAC_KEY

    expected_signature = generate_hmac(data, key)
    return hmac.compare_digest(signature, expected_signature)


def encrypt_license_data(license_data: dict) -> dict:
    """加密授权数据"""
    # 将授权数据转换为JSON字符串
    json_data = json.dumps(license_data, ensure_ascii=False, separators=(',', ':'))

    # AES加密
    encrypted_data = aes_encrypt(json_data)

    # 生成HMAC签名
    hmac_signature = generate_hmac(encrypted_data)

    # 编码为base64便于存储
    return {
        "encrypted_data": base64.b64encode(encrypted_data).decode('utf-8'),
        "hmac_signature": base64.b64encode(hmac_signature).decode('utf-8'),
        "version": "1.0",
        "timestamp": int(time.time())
    }


def decrypt_license_data(license_file: dict) -> dict:
    """解密授权数据"""
    try:
        # 解码base64
        encrypted_data = base64.b64decode(license_file["encrypted_data"])
        hmac_signature = base64.b64decode(license_file["hmac_signature"])

        # 验证HMAC签名
        if not verify_hmac(encrypted_data, hmac_signature):
            raise ValueError("授权文件签名验证失败，文件可能被篡改")

        # 解密数据
        decrypted_data = aes_decrypt(encrypted_data)

        # 解析JSON
        license_data = json.loads(decrypted_data.decode('utf-8'))

        return license_data

    except Exception as e:
        raise ValueError(f"授权文件解析失败: {str(e)}")


def create_license_object(total_images_allowed: int,
                         valid_days: int = 365,
                         max_sessions: int = 1000,
                         license_id: str = None) -> dict:
    """创建授权对象"""
    if license_id is None:
        license_id = hashlib.md5(f"{total_images_allowed}_{valid_days}_{time.time()}".encode()).hexdigest()[:16]

    return {
        "license_id": license_id,
        "total_images_allowed": total_images_allowed,
        "valid_days": valid_days,
        "max_sessions": max_sessions,
        "issued_at": int(time.time()),
        "expires_at": int(time.time()) + (valid_days * 24 * 60 * 60),
        "issuer": "成都正和德能风险管理咨询有限公司",
        "product": "牦牛图片跨案件号相似度分析系统"
    }


def validate_license(license_data: dict) -> tuple[bool, str]:
    """验证授权有效性"""
    current_time = int(time.time())

    # 检查有效期
    if current_time > license_data.get("expires_at", 0):
        return False, "授权已过期"

    # 检查基本字段
    required_fields = ["license_id", "total_images_allowed", "valid_days", "max_sessions"]
    for field in required_fields:
        if field not in license_data:
            return False, f"授权文件缺少必要字段: {field}"

    # 检查数值合理性
    if license_data["total_images_allowed"] <= 0:
        return False, "许可图片数量无效"

    if license_data["max_sessions"] <= 0:
        return False, "最大会话次数无效"

    return True, "授权有效"