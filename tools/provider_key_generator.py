#!/usr/bin/env python3
"""
乙方工具：根据甲方的使用量钥匙生成授权钥匙
"""

import os
import sys
import json
from dual_key_system import DualKeySystem

def main():
    """乙方生成授权钥匙"""
    print("=" * 60)
    print("乙方工具：根据甲方钥匙生成授权钥匙")
    print("=" * 60)
    
    try:
        # 初始化双钥匙系统
        dual_key = DualKeySystem()
        
        # 列出可用的客户端钥匙文件
        client_key_files = [f for f in os.listdir('.') if f.startswith('client_usage_key_') and f.endswith('.json')]
        
        if not client_key_files:
            print("❌ 未找到客户端钥匙文件")
            print("请确保甲方发送的钥匙文件在当前目录下")
            return
        
        print("发现以下客户端钥匙文件:")
        for i, filename in enumerate(client_key_files, 1):
            print(f"  {i}. {filename}")
        
        # 选择文件
        if len(client_key_files) == 1:
            selected_file = client_key_files[0]
            print(f"\n自动选择: {selected_file}")
        else:
            choice = input(f"\n请选择文件 (1-{len(client_key_files)}): ")
            try:
                idx = int(choice) - 1
                selected_file = client_key_files[idx]
            except (ValueError, IndexError):
                print("❌ 无效选择")
                return
        
        # 读取客户端钥匙
        with open(selected_file, 'r', encoding='utf-8') as f:
            client_key_data = f.read()
        
        # 解析客户端信息
        client_info = json.loads(client_key_data)
        print(f"\n📋 客户端信息:")
        print(f"   - 客户ID: {client_info.get('client_id', 'Unknown')}")
        print(f"   - 总处理图片: {client_info.get('total_images_processed', 0)} 张")
        print(f"   - 会话次数: {client_info.get('session_count', 0)} 次")
        print(f"   - 客户端IP: {client_info.get('client_ip', 'Unknown')}")
        print(f"   - 时间范围: {client_info.get('start_time', 'N/A')[:10]} 到 {client_info.get('end_time', 'N/A')[:10]}")
        
        # 乙方设置授权参数
        print(f"\n🔧 设置授权参数:")
        
        # 基础图片数量
        default_base = max(5000, client_info.get('total_images_processed', 0) * 2)
        base_images = input(f"   基础授权图片数 (默认 {default_base}): ").strip()
        base_images = int(base_images) if base_images else default_base
        
        # 有效期天数
        default_days = 30
        validity_days = input(f"   授权有效期天数 (默认 {default_days}): ").strip()
        validity_days = int(validity_days) if validity_days else default_days
        
        # 每日最大会话数
        default_sessions = 50
        max_sessions = input(f"   每日最大会话数 (默认 {default_sessions}): ").strip()
        max_sessions = int(max_sessions) if max_sessions else default_sessions
        
        # 授权参数
        auth_params = {
            'base_images': base_images,
            'validity_days': validity_days,
            'max_sessions_per_day': max_sessions
        }
        
        print(f"\n⚙️ 正在生成授权钥匙...")
        
        # 生成授权钥匙
        success, result = dual_key.generate_provider_key(client_key_data, auth_params)
        
        if success:
            # 解析生成的授权信息
            provider_info = json.loads(result)
            
            # 保存授权钥匙
            provider_key_filename = f"provider_auth_key_{provider_info['license_id']}.json"
            with open(provider_key_filename, 'w', encoding='utf-8') as f:
                f.write(result)
            
            print(f"✅ 授权钥匙生成成功！")
            print(f"📁 文件位置: {provider_key_filename}")
            print(f"📊 授权信息:")
            print(f"   - 授权ID: {provider_info['license_id']}")
            print(f"   - 允许图片数: {provider_info['total_images_allowed']:,} 张")
            print(f"   - 有效期: {provider_info['valid_from'][:10]} 到 {provider_info['valid_until'][:10]}")
            print(f"   - 允许IP: {', '.join(provider_info['allowed_ips'])}")
            print(f"   - 每日最大会话: {provider_info['max_sessions_per_day']} 次")
            
            print(f"\n📤 请将此授权钥匙文件发送给甲方")
            print(f"🔐 甲方需要将此文件通过系统界面上传才能获得使用权限")
            
            # 移动已处理的客户端钥匙到processed目录
            processed_dir = "processed_client_keys"
            os.makedirs(processed_dir, exist_ok=True)
            import shutil
            shutil.move(selected_file, os.path.join(processed_dir, selected_file))
            print(f"📦 客户端钥匙已移动到 {processed_dir}/ 目录")
            
        else:
            print(f"❌ 授权钥匙生成失败: {result}")
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()