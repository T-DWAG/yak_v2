#!/usr/bin/env python3
"""
创建测试授权文件
"""

import json
import os
from datetime import datetime, timedelta

def create_test_license():
    """创建测试授权文件"""
    
    # 创建license_data目录
    license_dir = "license_data"
    os.makedirs(license_dir, exist_ok=True)
    
    # 创建测试授权数据
    test_license = {
        "license_id": "TEST_LICENSE_20250822",
        "client_id": "QINGHAI_YAK_CLIENT_001",
        "total_images_allowed": 10000,  # 允许处理10000张图片
        "images_used": 0,
        "valid_until": (datetime.now() + timedelta(days=365)).isoformat(),  # 1年有效期
        "signature": "test_signature_qinghai_yak_2025"
    }
    
    # 保存授权文件
    license_file = os.path.join(license_dir, "license.json")
    with open(license_file, 'w', encoding='utf-8') as f:
        json.dump(test_license, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 测试授权文件已创建: {license_file}")
    print(f"📊 授权信息:")
    print(f"   - 授权ID: {test_license['license_id']}")
    print(f"   - 客户ID: {test_license['client_id']}")
    print(f"   - 允许图片数: {test_license['total_images_allowed']:,} 张")
    print(f"   - 已使用: {test_license['images_used']} 张")
    print(f"   - 有效期至: {test_license['valid_until'][:10]}")
    
    return license_file

if __name__ == "__main__":
    create_test_license()