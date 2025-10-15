#!/usr/bin/env python3
"""
牦牛图片分析系统初始授权文件生成器

使用方法:
    python generate_initial_license.py --images 10000 --days 365 --sessions 100

功能:
    生成初始授权文件（无需客户端钥匙）
    适用于首次部署或直接授权场景
"""

import argparse
import json
import sys
import os
from datetime import datetime

# 添加app目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.utils.crypto_utils import encrypt_license_data, create_license_object


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='牦牛图片分析系统初始授权文件生成器')

    parser.add_argument('--images', type=int, required=True,
                       help='许可图片总数量')
    parser.add_argument('--days', type=int, default=365,
                       help='有效期天数 (默认: 365)')
    parser.add_argument('--sessions', type=int, default=1000,
                       help='最大会话次数 (默认: 1000)')
    parser.add_argument('--output', default='license.json',
                       help='输出授权文件路径 (默认: license.json)')
    parser.add_argument('--license_id', default=None,
                       help='自定义授权ID (可选)')
    parser.add_argument('--client_name', default='',
                       help='客户名称 (可选)')

    return parser.parse_args()


def validate_arguments(args):
    """验证参数有效性"""
    # 验证数值参数
    if args.images <= 0:
        print("❌ 错误: 许可图片数量必须大于0")
        return False

    if args.days <= 0:
        print("❌ 错误: 有效期天数必须大于0")
        return False

    if args.sessions <= 0:
        print("❌ 错误: 会话次数必须大于0")
        return False

    return True


def generate_initial_license_file(args):
    """生成初始授权文件"""
    print("🔐 生成初始授权文件...")

    # 显示授权信息
    print(f"📜 授权信息:")
    print(f"   许可图片总数: {args.images} 张")
    print(f"   有效期: {args.days} 天")
    print(f"   最大会话次数: {args.sessions} 次")
    if args.client_name:
        print(f"   客户名称: {args.client_name}")

    # 创建授权对象
    license_data = create_license_object(
        total_images_allowed=args.images,
        valid_days=args.days,
        max_sessions=args.sessions,
        license_id=args.license_id
    )

    # 添加初始授权标识
    license_data["is_initial"] = True
    if args.client_name:
        license_data["client_name"] = args.client_name

    print(f"   授权ID: {license_data['license_id']}")
    print(f"   到期时间: {datetime.fromtimestamp(license_data['expires_at']).strftime('%Y-%m-%d %H:%M:%S')}")

    # 加密授权数据
    license_file = encrypt_license_data(license_data)

    return license_file


def save_license_file(license_file, output_path):
    """保存授权文件"""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(license_file, f, ensure_ascii=False, indent=2)

        print(f"✅ 初始授权文件已保存: {output_path}")
        return True
    except Exception as e:
        print(f"❌ 保存授权文件失败: {str(e)}")
        return False


def main():
    """主函数"""
    print("🔐 牦牛图片分析系统初始授权文件生成器")
    print("=" * 50)

    # 解析参数
    args = parse_arguments()

    # 验证参数
    if not validate_arguments(args):
        sys.exit(1)

    # 生成授权文件
    try:
        license_file = generate_initial_license_file(args)
    except Exception as e:
        print(f"❌ 生成授权文件失败: {str(e)}")
        sys.exit(1)

    # 保存授权文件
    if save_license_file(license_file, args.output):
        print("\n🎉 初始授权文件生成完成!")
        print(f"📁 输出文件: {args.output}")
        print("\n💡 使用说明:")
        print("   1. 将生成的授权文件上传到牦牛图片分析系统")
        print("   2. 系统将自动验证并应用新的授权设置")
        print("   3. 授权文件包含防篡改保护，请勿手动修改")
        print("   4. 后续可基于客户端钥匙生成续期授权文件")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()