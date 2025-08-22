#!/usr/bin/env python3
"""
乙方工具：为新客户生成初始授权钥匙
这是在没有使用记录的情况下生成的第一次授权
"""

import json
from datetime import datetime, timedelta
from dual_key_system import DualKeySystem

def generate_initial_license_for_new_client():
    """为新客户生成初始授权（无需客户端钥匙）"""
    print("=" * 60)
    print("乙方工具：为新客户生成初始授权钥匙")
    print("=" * 60)
    
    try:
        dual_key = DualKeySystem()
        
        # 新客户信息（乙方输入）
        print("\n请输入新客户信息:")
        client_id = input("客户ID (例: QINGHAI_YAK_CLIENT_001): ").strip()
        if not client_id:
            client_id = "NEW_CLIENT_001"
        
        # 初始授权参数（乙方决定）
        print("\n设置初始授权参数:")
        
        initial_images = input("初始图片配额 (默认 1000): ").strip()
        initial_images = int(initial_images) if initial_images else 1000
        
        validity_days = input("有效期天数 (默认 30): ").strip() 
        validity_days = int(validity_days) if validity_days else 30
        
        max_sessions = input("每日最大会话数 (默认 20): ").strip()
        max_sessions = int(max_sessions) if max_sessions else 20
        
        # 创建初始客户端数据（模拟）
        mock_client_data = {
            'client_id': client_id,
            'total_images_processed': 0,  # 新客户没有历史记录
            'total_records': 0,
            'first_use_time': datetime.now().isoformat(),
            'last_use_time': datetime.now().isoformat()
        }
        
        # 初始授权参数
        auth_params = {
            'base_images': initial_images,
            'validity_days': validity_days,
            'max_sessions_per_day': max_sessions
        }
        
        print(f"\n正在为新客户 {client_id} 生成初始授权...")
        
        # 生成初始授权钥匙
        success, initial_license = dual_key.generate_provider_key(
            json.dumps(mock_client_data), auth_params
        )
        
        if success:
            # 保存初始授权文件
            license_filename = f"initial_license_{client_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(license_filename, 'w', encoding='utf-8') as f:
                f.write(initial_license)
            
            license_data = json.loads(initial_license)
            
            print(f"\n✅ 初始授权钥匙生成成功！")
            print(f"📁 文件位置: {license_filename}")
            print(f"📊 授权信息:")
            print(f"   - 客户ID: {license_data['client_id']}")
            print(f"   - 授权ID: {license_data['license_id']}")
            print(f"   - 初始配额: {license_data['total_images_allowed']:,} 张图片")
            print(f"   - 有效期: {license_data['valid_from'][:10]} 到 {license_data['valid_until'][:10]}")
            print(f"   - 每日会话: {license_data['max_sessions_per_day']} 次")
            print(f"   - 允许IP: {', '.join(license_data['allowed_ips'])}")
            
            print(f"\n📤 请将此初始授权文件发送给客户")
            print(f"🔑 客户使用此文件即可开始使用系统")
            
            return True
            
        else:
            print(f"❌ 初始授权生成失败: {initial_license}")
            return False
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    success = generate_initial_license_for_new_client()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 初始授权钥匙生成完成！")
        print("\n📋 使用流程:")
        print("1. 将生成的初始授权文件发送给新客户")
        print("2. 客户通过Web界面上传此文件")
        print("3. 客户开始使用系统处理图片")
        print("4. 后续使用双钥匙流程进行授权续费")
    else:
        print("❌ 初始授权钥匙生成失败！")
    
    print("=" * 60)
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)