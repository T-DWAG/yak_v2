"""
简化版授权管理器 - 移除cryptography依赖
Linus风格的简洁实现，专注核心功能
"""

import os
import json
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class UsageRecord:
    """使用量记录 - 核心数据结构"""
    timestamp: str
    images_processed: int
    session_id: str
    start_time: str
    end_time: str
    prev_hash: str  # 前一条记录的哈希值，构成哈希链
    record_hash: str  # 当前记录的哈希值（防篡改）

@dataclass
class LicenseInfo:
    """授权信息"""
    license_id: str
    client_id: str
    total_images_allowed: int
    images_used: int
    valid_until: str
    signature: str  # 简单签名

class LicenseManager:
    """授权管理器 - Linus风格的简洁实现（无cryptography依赖）"""
    
    def __init__(self, data_dir: str = "license_data"):
        self.data_dir = data_dir
        self.usage_log_file = os.path.join(data_dir, "usage_log.json")
        self.license_file = os.path.join(data_dir, "license.json")
        
        # 确保目录存在
        os.makedirs(data_dir, exist_ok=True)
        
        # 内存中的状态
        self._usage_records: List[UsageRecord] = []
        self._current_license: Optional[LicenseInfo] = None
        self._load_data()
    
    def _load_data(self):
        """加载现有数据"""
        # 加载使用记录
        if os.path.exists(self.usage_log_file):
            try:
                with open(self.usage_log_file, 'r', encoding='utf-8') as f:
                    records_data = json.load(f)
                    self._usage_records = [UsageRecord(**record) for record in records_data]
                logger.info(f"已加载 {len(self._usage_records)} 条使用记录")
            except Exception as e:
                logger.error(f"加载使用记录失败: {e}")
                self._usage_records = []
        
        # 加载授权信息
        if os.path.exists(self.license_file):
            try:
                with open(self.license_file, 'r', encoding='utf-8') as f:
                    license_data = json.load(f)
                    self._current_license = LicenseInfo(**license_data)
                logger.info(f"已加载授权信息: {self._current_license.license_id}")
            except Exception as e:
                logger.error(f"加载授权信息失败: {e}")
    
    def _calculate_record_hash(self, record: UsageRecord) -> str:
        """计算记录哈希值 - 防篡改的核心"""
        # 除了record_hash字段外的所有数据
        data = {
            'timestamp': record.timestamp,
            'images_processed': record.images_processed,
            'session_id': record.session_id,
            'start_time': record.start_time,
            'end_time': record.end_time,
            'prev_hash': record.prev_hash
        }
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def _validate_hash_chain(self) -> bool:
        """验证哈希链完整性"""
        if not self._usage_records:
            return True
            
        for i, record in enumerate(self._usage_records):
            # 验证当前记录的哈希值
            expected_hash = self._calculate_record_hash(record)
            if record.record_hash != expected_hash:
                logger.error(f"记录 {i} 哈希验证失败")
                return False
            
            # 验证哈希链
            if i > 0:
                prev_record = self._usage_records[i-1]
                if record.prev_hash != prev_record.record_hash:
                    logger.error(f"记录 {i} 哈希链断裂")
                    return False
        
        return True
    
    def check_authorization(self) -> Tuple[bool, str]:
        """检查授权状态"""
        # 验证哈希链完整性
        if not self._validate_hash_chain():
            return False, "使用记录被篡改，请联系供应商"
        
        # 检查是否有授权
        if not self._current_license:
            return False, "未找到授权文件，请联系供应商获取授权"
        
        # 检查授权是否过期
        try:
            valid_until = datetime.fromisoformat(self._current_license.valid_until)
            if datetime.now() > valid_until:
                return False, f"授权已过期（{self._current_license.valid_until}），请联系供应商续费"
        except:
            return False, "授权文件格式错误"
        
        # 检查使用量
        if self._current_license.images_used >= self._current_license.total_images_allowed:
            return False, f"已达到授权图片数量上限（{self._current_license.total_images_allowed}张），请联系供应商增加授权"
        
        return True, "授权正常"
    
    def record_usage(self, images_processed: int, session_id: str, start_time: str, end_time: str) -> bool:
        """记录使用量"""
        try:
            timestamp = datetime.now().isoformat()
            
            # 获取前一条记录的哈希值
            prev_hash = ""
            if self._usage_records:
                prev_hash = self._usage_records[-1].record_hash
            
            # 创建新记录（先不设置record_hash）
            new_record = UsageRecord(
                timestamp=timestamp,
                images_processed=images_processed,
                session_id=session_id,
                start_time=start_time,
                end_time=end_time,
                prev_hash=prev_hash,
                record_hash=""  # 临时值
            )
            
            # 计算并设置哈希值
            new_record.record_hash = self._calculate_record_hash(new_record)
            
            # 添加到记录列表
            self._usage_records.append(new_record)
            
            # 更新授权使用量
            if self._current_license:
                self._current_license.images_used += images_processed
                self._save_license()
            
            # 保存使用记录
            self._save_usage_records()
            
            logger.info(f"已记录使用量: {images_processed} 张图片")
            return True
            
        except Exception as e:
            logger.error(f"记录使用量失败: {e}")
            return False
    
    def _save_usage_records(self):
        """保存使用记录"""
        try:
            records_data = [asdict(record) for record in self._usage_records]
            with open(self.usage_log_file, 'w', encoding='utf-8') as f:
                json.dump(records_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存使用记录失败: {e}")
    
    def _save_license(self):
        """保存授权信息"""
        if self._current_license:
            try:
                with open(self.license_file, 'w', encoding='utf-8') as f:
                    json.dump(asdict(self._current_license), f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"保存授权信息失败: {e}")
    
    def generate_usage_report(self) -> str:
        """生成使用量报告（简化版）"""
        if not self._usage_records:
            return ""
        
        # 统计数据
        total_images = sum(record.images_processed for record in self._usage_records)
        total_sessions = len(self._usage_records)
        first_use = self._usage_records[0].timestamp
        last_use = self._usage_records[-1].timestamp
        
        # 构建报告数据（先不包含signature）
        report_data = {
            "client_id": getattr(self._current_license, 'client_id', 'unknown'),
            "total_images_processed": total_images,
            "total_sessions": total_sessions,
            "first_use_time": first_use,
            "last_use_time": last_use,
            "report_generated_time": datetime.now().isoformat(),
            "hash_chain_valid": self._validate_hash_chain(),
            "records_count": len(self._usage_records)
        }
        
        # 生成签名
        data_for_signature = json.dumps(report_data, sort_keys=True)
        signature = "simple_hash_" + hashlib.md5(data_for_signature.encode()).hexdigest()[:16]
        report_data["signature"] = signature
        
        return json.dumps(report_data, indent=2, ensure_ascii=False)
    
    def load_private_license(self, private_key_data: str) -> bool:
        """加载私钥授权文件（支持双钥匙系统）"""
        try:
            # 解析私钥数据
            license_data = json.loads(private_key_data)
            
            # 检查是否是双钥匙系统的授权
            if 'provider_signature' in license_data and license_data.get('provider_signature', '').startswith('PROVIDER_'):
                return self._load_dual_key_license(license_data)
            
            # 传统授权文件处理
            # 验证必要字段
            required_fields = ['license_id', 'client_id', 'total_images_allowed', 'valid_until', 'signature']
            for field in required_fields:
                if field not in license_data:
                    logger.error(f"授权文件缺少必要字段: {field}")
                    return False
            
            # 创建授权信息
            self._current_license = LicenseInfo(
                license_id=license_data['license_id'],
                client_id=license_data['client_id'],
                total_images_allowed=license_data['total_images_allowed'],
                images_used=license_data.get('images_used', 0),
                valid_until=license_data['valid_until'],
                signature=license_data['signature']
            )
            
            # 保存授权文件
            self._save_license()
            
            logger.info(f"传统授权加载成功: {self._current_license.license_id}")
            return True
            
        except Exception as e:
            logger.error(f"加载授权失败: {e}")
            return False
    
    def _load_dual_key_license(self, provider_key_data: dict) -> bool:
        """加载双钥匙系统的授权"""
        try:
            from dual_key_system import DualKeySystem
            
            # 验证乙方授权钥匙
            dual_key = DualKeySystem()
            auth_ok, auth_msg = dual_key.verify_provider_key(json.dumps(provider_key_data))
            
            if not auth_ok:
                logger.error(f"双钥匙授权验证失败: {auth_msg}")
                return False
            
            # 转换为系统授权格式
            license_data = dual_key.convert_to_license_format(json.dumps(provider_key_data))
            
            if not license_data:
                logger.error("双钥匙授权格式转换失败")
                return False
            
            # 创建授权信息
            self._current_license = LicenseInfo(
                license_id=license_data['license_id'],
                client_id=license_data['client_id'],
                total_images_allowed=license_data['total_images_allowed'],
                images_used=license_data.get('images_used', 0),
                valid_until=license_data['valid_until'],
                signature=license_data['signature']
            )
            
            # 保存授权文件
            self._save_license()
            
            logger.info(f"双钥匙授权加载成功: {self._current_license.license_id}")
            return True
            
        except Exception as e:
            logger.error(f"加载双钥匙授权失败: {e}")
            return False
    
    def get_usage_stats(self) -> Dict:
        """获取使用统计信息"""
        stats = {
            "total_records": len(self._usage_records),
            "total_images_processed": sum(record.images_processed for record in self._usage_records),
            "hash_chain_valid": self._validate_hash_chain()
        }
        
        if self._current_license:
            stats.update({
                "license_id": self._current_license.license_id,
                "client_id": self._current_license.client_id,
                "total_images_allowed": self._current_license.total_images_allowed,
                "images_used": self._current_license.images_used,
                "images_remaining": self._current_license.total_images_allowed - self._current_license.images_used,
                "valid_until": self._current_license.valid_until
            })
        
        return stats
    
    def export_usage_report_file(self) -> str:
        """导出使用量报告文件"""
        report = self.generate_usage_report()
        if report:
            report_file = os.path.join(self.data_dir, f"usage_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            try:
                with open(report_file, 'w', encoding='utf-8') as f:
                    f.write(report)
                logger.info(f"使用量报告已导出: {report_file}")
                return report_file
            except Exception as e:
                logger.error(f"导出报告失败: {e}")
        return ""