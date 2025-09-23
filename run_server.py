#!/usr/bin/env python3
"""
正确的服务启动脚本
从project目录启动，确保模块导入正确
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.server:app", host="0.0.0.0", port=8000, reload=True)
