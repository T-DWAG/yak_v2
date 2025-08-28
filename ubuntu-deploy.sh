#!/bin/bash
# Ubuntu一键部署脚本 - Yak Similarity Analyzer
# 支持 Ubuntu 18.04+ / Debian 10+

set -e

echo "=============================================="
echo "🐂 Yak Similarity Analyzer Ubuntu 部署脚本"
echo "=============================================="

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否为root或sudo权限
if [[ $EUID -eq 0 ]]; then
    echo -e "${YELLOW}检测到root权限，建议使用普通用户运行${NC}"
    read -p "是否继续? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 步骤1: 系统更新
echo -e "${GREEN}[1/8] 更新系统包...${NC}"
sudo apt-get update
sudo apt-get upgrade -y

# 步骤2: 安装Python和pip
echo -e "${GREEN}[2/8] 安装Python环境...${NC}"
sudo apt-get install -y python3 python3-pip python3-venv curl wget git

# 验证Python版本
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
echo "Python版本: $PYTHON_VERSION"

if [[ $(echo "$PYTHON_VERSION >= 3.9" | bc -l) -eq 0 ]]; then
    echo -e "${RED}警告: Python版本低于3.9，可能存在兼容性问题${NC}"
fi

# 步骤3: 安装系统依赖
echo -e "${GREEN}[3/8] 安装系统依赖...${NC}"
sudo apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libfontconfig1 \
    libgcc-s1

# 步骤4: 创建应用目录
echo -e "${GREEN}[4/8] 创建应用目录...${NC}"
APP_DIR="$HOME/yak-analyzer"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# 步骤5: 克隆代码
echo -e "${GREEN}[5/8] 下载应用代码...${NC}"
if [ -d "yak_v2" ]; then
    echo "代码目录已存在，更新中..."
    cd yak_v2
    git pull origin main
else
    git clone https://github.com/T-DWAG/yak_v2.git
    cd yak_v2
fi

# 步骤6: 创建Python虚拟环境
echo -e "${GREEN}[6/8] 创建Python虚拟环境...${NC}"
python3 -m venv venv
source venv/bin/activate

# 升级pip
pip install --upgrade pip

# 步骤7: 安装Python依赖
echo -e "${GREEN}[7/8] 安装Python依赖...${NC}"
# 安装基础依赖（不包含重型包）
pip install flask==3.0.0 werkzeug==3.0.1 pillow>=10.0.0 imagehash>=4.3.1

# 询问是否安装YOLO相关依赖
echo -e "${YELLOW}是否安装YOLO相关依赖? (需要更多时间和空间)${NC}"
read -p "安装YOLO? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "正在安装YOLO依赖..."
    pip install ultralytics>=8.0.0 torch>=1.13.0 torchvision>=0.14.0
else
    echo "跳过YOLO依赖，将使用Mock模式"
fi

# 步骤8: 创建必要目录和权限
echo -e "${GREEN}[8/8] 配置应用...${NC}"
mkdir -p data uploads results license_data dual_keys
chmod +x docker-start.sh
chmod +x ubuntu-deploy.sh

# 创建systemd服务文件
echo -e "${GREEN}创建系统服务...${NC}"
sudo tee /etc/systemd/system/yak-analyzer.service > /dev/null <<EOF
[Unit]
Description=Yak Similarity Analyzer
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR/yak_v2
Environment=PATH=$APP_DIR/yak_v2/venv/bin
Environment=PYTHONPATH=$APP_DIR/yak_v2/src
ExecStart=$APP_DIR/yak_v2/venv/bin/python run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 启用服务
sudo systemctl daemon-reload
sudo systemctl enable yak-analyzer

echo
echo "=============================================="
echo -e "${GREEN}✅ 部署完成！${NC}"
echo "=============================================="
echo
echo "🚀 启动服务:"
echo "   sudo systemctl start yak-analyzer"
echo
echo "📊 查看状态:"
echo "   sudo systemctl status yak-analyzer"
echo
echo "📝 查看日志:"
echo "   sudo journalctl -u yak-analyzer -f"
echo
echo "🌐 访问地址:"
echo "   http://localhost:5000"
echo "   http://$(hostname -I | awk '{print $1}'):5000"
echo
echo "🔑 双钥匙测试:"
echo "   cd $APP_DIR/yak_v2"
echo "   source venv/bin/activate"
echo "   python tools/client_key_generator.py"
echo "   python tools/provider_key_generator.py client_key.json"
echo
echo "🛑 停止服务:"
echo "   sudo systemctl stop yak-analyzer"
echo
echo "=============================================="