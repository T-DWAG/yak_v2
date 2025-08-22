#!/usr/bin/env python3
"""
Yak Similarity Analyzer - Main Entry Point
快速启动脚本
"""

import os
import sys

# 添加src目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

def main():
    """主启动函数"""
    print("=" * 60)
    print("Yak Image Cross-Case Similarity Analyzer")
    print("Version: 2.0.0")
    print("=" * 60)
    
    try:
        # 导入并运行主应用
        from app import app, init_system
        
        print("Initializing system...")
        init_system()
        
        print("Starting web server...")
        print("Access URL: http://127.0.0.1:5000")
        print("Press Ctrl+C to stop")
        print("-" * 60)
        
        # 启动Flask应用
        app.run(
            debug=False,  # 生产环境关闭debug
            host='0.0.0.0',
            port=5000,
            threaded=True
        )
        
    except KeyboardInterrupt:
        print("\nSystem stopped")
    except Exception as e:
        print(f"Startup failed: {e}")
        print("\nPlease check:")
        print("1. Python environment is correct")
        print("2. Dependencies installed: pip install -r requirements.txt")
        print("3. Model files exist")
        sys.exit(1)

if __name__ == "__main__":
    main()