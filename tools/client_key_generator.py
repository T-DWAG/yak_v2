#!/usr/bin/env python3
"""
甲方工具：生成使用量钥匙发送给乙方
"""

import os
import sys

# 添加src目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, '..', 'src')
sys.path.insert(0, src_dir)

from dual_key_system import DualKeySystem

def main():
    """甲方生成使用量钥匙"""
    print("=" * 60)
    print("甲方工具：生成使用量钥匙")
    print("=" * 60)
    
    try:
        # 初始化双钥匙系统
        dual_key = DualKeySystem()
        
        # 获取当前使用量统计
        usage_stats = dual_key.get_client_usage_summary()
        
        print("当前使用量统计:")
        print(f"  - 总处理图片: {usage_stats.get('total_images_processed', 0)} 张")
        print(f"  - 会话次数: {usage_stats.get('total_records', 0)} 次")
        print(f"  - 哈希链验证: {'通过' if usage_stats.get('hash_chain_valid', False) else '失败'}")
        
        if usage_stats.get('total_images_processed', 0) == 0:
            print("\n警告：没有使用记录，建议先运行一些图片处理任务")
            choice = input("是否继续生成钥匙？(y/N): ")
            if choice.lower() != 'y':
                return
        
        # 生成客户端钥匙
        print("\n正在生成使用量钥匙...")
        client_key = dual_key.create_client_key(usage_stats)
        
        if client_key:
            # 保存到文件
            key_filename = f"client_usage_key_{dual_key._get_client_ip()}_{usage_stats.get('total_images_processed', 0)}.json"
            with open(key_filename, 'w', encoding='utf-8') as f:
                f.write(client_key)
            
            print(f"\n✅ 使用量钥匙生成成功！")
            print(f"📁 文件位置: {key_filename}")
            print(f"📊 包含信息:")
            print(f"   - 总处理图片: {usage_stats.get('total_images_processed', 0)} 张")
            print(f"   - 会话次数: {usage_stats.get('total_records', 0)} 次")
            print(f"   - 客户端IP: {dual_key._get_client_ip()}")
            print(f"   - 时间范围: {usage_stats.get('first_use_time', 'N/A')[:10]} 到 {usage_stats.get('last_use_time', 'N/A')[:10]}")
            
            print(f"\n📤 请将此文件发送给乙方以获取新的授权钥匙")
            
        else:
            print("❌ 使用量钥匙生成失败")
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # 测试模式，不实际生成文件
        print("Test mode: client key generator working")
        sys.exit(0)
    else:
        main()