#!/bin/bash
# Linux快速启动脚本

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=============================================="
echo -e "${GREEN}🐂 Yak Similarity Analyzer - Linux启动${NC}"
echo "=============================================="

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 需要安装Python3${NC}"
    echo "Ubuntu/Debian: sudo apt-get install python3 python3-pip python3-venv"
    echo "CentOS/RHEL: sudo yum install python3 python3-pip"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}创建Python虚拟环境...${NC}"
    python3 -m venv venv
fi

# 激活虚拟环境
echo -e "${GREEN}激活虚拟环境...${NC}"
source venv/bin/activate

# 安装基础依赖
echo -e "${GREEN}检查Python依赖...${NC}"
pip install flask pillow imagehash --quiet || {
    echo -e "${YELLOW}安装基础依赖...${NC}"
    pip install flask==3.0.0 pillow>=10.0.0 imagehash>=4.3.1
}

# 创建必要目录
mkdir -p uploads results data license_data dual_keys

# 设置环境变量
export PYTHONPATH="$(pwd)/src"
export FLASK_ENV="production"

# 检查端口占用
if netstat -tuln | grep -q ":5000 "; then
    echo -e "${YELLOW}警告: 端口5000已被占用${NC}"
    read -p "是否继续? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo -e "${GREEN}启动应用...${NC}"
echo "访问地址: http://localhost:5000"
echo "按 Ctrl+C 停止服务"
echo "=============================================="

# 启动应用
python run.py