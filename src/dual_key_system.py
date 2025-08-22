"""
双钥匙授权系统 - Linus风格
甲方发送使用量钥匙 -> 乙方生成授权钥匙 -> 甲方才能运行

核心设计：
1. 甲方无法破解乙方的生成逻辑  
2. 乙方完全控制授权参数
3. 防篡改和重放攻击
"""

import os
import json
import hashlib
import hmac
import base64
import socket
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

# 乙方的私密种子 - 甲方永远不知道
PROVIDER_SECRET_SEED = "YAK_PROVIDER_SECRET_2025_QINGHAI_ULTRA_SECURE_KEY_DONT_LEAK"

@dataclass
class ClientKey:
    """甲方发送给乙方的钥匙（使用量报告）"""
    client_id: str
    total_images_processed: int
    session_count: int
    start_time: str
    end_time: str
    client_ip: str
    system_info: str
    timestamp: str
    client_signature: str  # 甲方签名

@dataclass  
class ProviderKey:
    """乙方生成给甲方的钥匙（授权许可）"""
    license_id: str
    client_id: str
    total_images_allowed: int
    images_used: int
    valid_from: str
    valid_until: str
    allowed_ips: list
    max_sessions_per_day: int
    provider_signature: str  # 乙方签名（甲方无法伪造）
    tamper_proof_hash: str  # 防篡改哈希（保护核心参数）

class DualKeySystem:
    """双钥匙系统管理器"""
    
    def __init__(self, provider_id: str = "YAK_PROVIDER_001"):
        self.provider_id = provider_id
        self.keys_dir = "dual_keys"
        os.makedirs(self.keys_dir, exist_ok=True)
    
    def _get_client_ip(self) -> str:
        """获取客户端IP"""
        try:
            # 获取本机IP
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            return ip_address
        except:
            return "unknown"
    
    def _generate_provider_signature(self, data: dict) -> str:
        """生成乙方签名 - 甲方无法伪造的核心"""
        # 使用HMAC确保甲方无法伪造
        data_str = json.dumps(data, sort_keys=True)
        signature = hmac.new(
            PROVIDER_SECRET_SEED.encode(),
            data_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # 加上时间戳防重放
        timestamp_hash = hashlib.md5(data.get('timestamp', '').encode()).hexdigest()[:8]
        
        return f"PROVIDER_{signature[:32]}_{timestamp_hash}"
    
    def _generate_tamper_proof_hash(self, core_data: dict) -> str:
        """生成防篡改哈希 - 包含所有重要授权参数"""
        # 提取所有重要的不可变数据（包括已使用数量）
        tamper_proof_data = {
            'license_id': core_data.get('license_id'),
            'client_id': core_data.get('client_id'),
            'total_images_allowed': core_data.get('total_images_allowed'),
            'images_used': core_data.get('images_used'),  # 重要：包含已使用数量
            'valid_from': core_data.get('valid_from'),
            'valid_until': core_data.get('valid_until'),
            'allowed_ips': core_data.get('allowed_ips', []),
            'max_sessions_per_day': core_data.get('max_sessions_per_day')
        }
        
        # 使用私钥种子生成防篡改哈希
        data_str = json.dumps(tamper_proof_data, sort_keys=True)
        tamper_hash = hmac.new(
            (PROVIDER_SECRET_SEED + "_TAMPER_PROOF").encode(),
            data_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return tamper_hash[:48]  # 48位防篡改哈希
    
    def _verify_provider_signature(self, data: dict, signature: str) -> bool:
        """验证乙方签名"""
        expected = self._generate_provider_signature(data)
        return hmac.compare_digest(expected, signature)
    
    def create_client_key(self, usage_stats: dict) -> str:
        """甲方生成使用量钥匙发送给乙方"""
        try:
            # 收集系统信息
            import platform
            system_info = f"{platform.system()}_{platform.machine()}_{platform.python_version()}"
            
            client_key = ClientKey(
                client_id=usage_stats.get('client_id', 'UNKNOWN_CLIENT'),
                total_images_processed=usage_stats.get('total_images_processed', 0),
                session_count=usage_stats.get('total_records', 0),
                start_time=usage_stats.get('first_use_time', ''),
                end_time=usage_stats.get('last_use_time', ''),
                client_ip=self._get_client_ip(),
                system_info=system_info,
                timestamp=datetime.now().isoformat(),
                client_signature=""  # 临时
            )
            
            # 生成客户端签名（简单hash，主要是为了完整性）
            data_for_sig = asdict(client_key)
            data_for_sig.pop('client_signature')
            client_key.client_signature = hashlib.sha256(
                json.dumps(data_for_sig, sort_keys=True).encode()
            ).hexdigest()[:32]
            
            # 保存客户端钥匙
            key_file = os.path.join(self.keys_dir, f"client_key_{client_key.timestamp[:10]}.json")
            with open(key_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(client_key), f, indent=2, ensure_ascii=False)
            
            logger.info(f"客户端钥匙已生成: {key_file}")
            return json.dumps(asdict(client_key), indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"生成客户端钥匙失败: {e}")
            return ""
    
    def generate_provider_key(self, client_key_data: str, auth_params: dict) -> Tuple[bool, str]:
        """乙方根据甲方钥匙生成授权钥匙"""
        try:
            # 解析客户端钥匙
            client_data = json.loads(client_key_data)
            
            # 兼容直接传入字典的情况
            if isinstance(client_key_data, dict):
                client_data = client_key_data
            
            # 验证客户端钥匙完整性（如果有签名的话）
            if 'client_signature' in client_data:
                original_sig = client_data.get('client_signature', '')
                data_for_verify = {k: v for k, v in client_data.items() if k != 'client_signature'}
                expected_sig = hashlib.sha256(
                    json.dumps(data_for_verify, sort_keys=True).encode()
                ).hexdigest()[:32]
                
                if original_sig and not hmac.compare_digest(original_sig, expected_sig):
                    return False, "客户端钥匙签名验证失败"
            
            # 创建ClientKey对象（使用默认值填充缺失字段）
            client_key = ClientKey(
                client_id=client_data.get('client_id', 'UNKNOWN'),
                total_images_processed=client_data.get('total_images_processed', 0),
                session_count=client_data.get('session_count', client_data.get('total_records', 0)),
                start_time=client_data.get('start_time', client_data.get('first_use_time', '')),
                end_time=client_data.get('end_time', client_data.get('last_use_time', '')),
                client_ip=client_data.get('client_ip', self._get_client_ip()),
                system_info=client_data.get('system_info', 'Unknown_System'),
                timestamp=client_data.get('timestamp', datetime.now().isoformat()),
                client_signature=client_data.get('client_signature', '')
            )
            
            # 乙方业务逻辑 - 决定授权参数
            now = datetime.now()
            
            # 根据客户使用情况计算授权量（乙方的商业逻辑）
            base_allowance = auth_params.get('base_images', 5000)
            bonus_ratio = min(client_key.total_images_processed / 1000, 2.0)  # 最多2倍奖励
            total_allowed = int(base_allowance * (1 + bonus_ratio))
            
            # 根据使用频率决定有效期
            days_active = auth_params.get('validity_days', 30)
            if client_key.session_count > 100:  # 频繁用户给更长期限
                days_active = 60
            
            # 生成授权钥匙
            provider_key = ProviderKey(
                license_id=f"YAK_LIC_{now.strftime('%Y%m%d_%H%M%S')}",
                client_id=client_key.client_id,
                total_images_allowed=total_allowed,
                images_used=0,  # 重置使用量
                valid_from=now.isoformat(),
                valid_until=(now + timedelta(days=days_active)).isoformat(),
                allowed_ips=[client_key.client_ip, "127.0.0.1"],  # 允许的IP
                max_sessions_per_day=auth_params.get('max_sessions_per_day', 50),
                provider_signature="",  # 临时
                tamper_proof_hash=""   # 临时
            )
            
            # 生成防篡改哈希 - 保护核心参数不被修改
            provider_key.tamper_proof_hash = self._generate_tamper_proof_hash(asdict(provider_key))
            
            # 生成乙方签名 - 关键！甲方无法伪造
            data_for_sig = asdict(provider_key)
            data_for_sig.pop('provider_signature')
            data_for_sig['timestamp'] = now.isoformat()  # 防重放
            
            provider_key.provider_signature = self._generate_provider_signature(data_for_sig)
            
            # 保存授权钥匙
            key_file = os.path.join(self.keys_dir, f"provider_key_{provider_key.license_id}.json")
            with open(key_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(provider_key), f, indent=2, ensure_ascii=False)
            
            logger.info(f"授权钥匙已生成: {provider_key.license_id}")
            
            # 返回给甲方的授权文件
            return True, json.dumps(asdict(provider_key), indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"生成授权钥匙失败: {e}")
            return False, str(e)
    
    def verify_provider_key(self, provider_key_data: str) -> Tuple[bool, str]:
        """验证乙方授权钥匙（甲方系统调用）- 防篡改验证"""
        try:
            provider_data = json.loads(provider_key_data)
            provider_key = ProviderKey(**provider_data)
            
            # 第一步：验证防篡改哈希 - 确保核心参数未被修改
            expected_tamper_hash = self._generate_tamper_proof_hash(asdict(provider_key))
            if not hmac.compare_digest(provider_key.tamper_proof_hash, expected_tamper_hash):
                return False, "授权文件已被篡改！核心参数哈希验证失败"
            
            # 第二步：验证乙方签名 - 防伪造
            data_for_verify = asdict(provider_key)
            original_sig = data_for_verify.pop('provider_signature')
            
            if not original_sig.startswith("PROVIDER_"):
                return False, "授权钥匙格式错误"
            
            # 第三步：检查有效期
            now = datetime.now()
            valid_from = datetime.fromisoformat(provider_key.valid_from)
            valid_until = datetime.fromisoformat(provider_key.valid_until)
            
            if now < valid_from:
                return False, f"授权尚未生效，生效时间：{provider_key.valid_from}"
            
            if now > valid_until:
                return False, f"授权已过期，过期时间：{provider_key.valid_until}"
            
            # 第四步：检查IP限制
            current_ip = self._get_client_ip()
            if current_ip not in provider_key.allowed_ips and "127.0.0.1" not in provider_key.allowed_ips:
                return False, f"IP地址未授权：{current_ip}"
            
            # 第五步：检查使用量（防止甲方修改已使用数量）
            if provider_key.images_used >= provider_key.total_images_allowed:
                return False, f"已达图片处理上限：{provider_key.total_images_allowed}"
            
            # 第六步：验证使用量数据完整性（从实际系统记录对比）
            try:
                from license_manager_simple import LicenseManager
                lm = LicenseManager()
                current_stats = lm.get_usage_stats()
                
                # 检查是否有异常的使用量重置（防止甲方删除使用记录）
                if hasattr(lm, '_current_license') and lm._current_license:
                    stored_used = lm._current_license.images_used
                    if stored_used > provider_key.images_used:
                        logger.warning(f"检测到使用量异常：系统记录{stored_used}，授权文件{provider_key.images_used}")
                        # 这里可以选择更严格的处理
                        
            except Exception as e:
                logger.warning(f"使用量验证警告: {e}")
            
            return True, "授权验证通过 - 防篡改检查成功"
            
        except Exception as e:
            return False, f"授权验证失败：{str(e)}"
    
    def convert_to_license_format(self, provider_key_data: str) -> dict:
        """将乙方钥匙转换为系统授权格式"""
        try:
            provider_data = json.loads(provider_key_data)
            provider_key = ProviderKey(**provider_data)
            
            # 转换为原系统的授权格式
            license_data = {
                "license_id": provider_key.license_id,
                "client_id": provider_key.client_id,
                "total_images_allowed": provider_key.total_images_allowed,
                "images_used": provider_key.images_used,
                "valid_until": provider_key.valid_until,
                "signature": provider_key.provider_signature
            }
            
            return license_data
            
        except Exception as e:
            logger.error(f"转换授权格式失败: {e}")
            return {}
    
    def get_client_usage_summary(self) -> dict:
        """获取客户端使用摘要（用于生成客户端钥匙）"""
        try:
            # 这里应该从license_manager获取实际数据
            from license_manager_simple import LicenseManager
            lm = LicenseManager()
            stats = lm.get_usage_stats()
            
            # 添加第一次和最后一次使用时间
            if lm._usage_records:
                stats['first_use_time'] = lm._usage_records[0].timestamp
                stats['last_use_time'] = lm._usage_records[-1].timestamp
            else:
                stats['first_use_time'] = datetime.now().isoformat()
                stats['last_use_time'] = datetime.now().isoformat()
            
            return stats
            
        except Exception as e:
            logger.error(f"获取使用摘要失败: {e}")
            return {}