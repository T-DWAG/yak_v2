# 🐧 Ubuntu Linux 一键部署指南

## 🚀 最简单部署方式（推荐）

### 一键部署脚本
```bash
# 下载并执行一键部署
curl -fsSL https://raw.githubusercontent.com/T-DWAG/yak_v2/main/ubuntu-deploy.sh | bash
```

或手动下载：
```bash
wget https://github.com/T-DWAG/yak_v2/archive/main.zip
unzip main.zip
cd yak_v2-main
chmod +x ubuntu-deploy.sh
./ubuntu-deploy.sh
```

## 🐳 Docker部署（Ubuntu优化）

### 方法1: Docker Compose
```bash
git clone https://github.com/T-DWAG/yak_v2.git
cd yak_v2
docker-compose -f docker-compose.ubuntu.yml up --build -d
```

### 方法2: 直接Docker
```bash
git clone https://github.com/T-DWAG/yak_v2.git
cd yak_v2
docker build -f Dockerfile.ubuntu -t yak-analyzer .
docker run -d -p 5000:5000 -v $(pwd)/data:/app/data yak-analyzer
```

## 📋 系统要求

### 支持的系统
- Ubuntu 18.04 LTS+
- Ubuntu 20.04 LTS+
- Ubuntu 22.04 LTS+
- Debian 10+

### 硬件要求
- CPU: 2核心以上
- RAM: 2GB以上（4GB推荐）
- 硬盘: 5GB可用空间
- 网络: 互联网连接（用于下载依赖）

## 🛠️ 手动部署步骤

### 步骤1: 系统准备
```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础工具
sudo apt install -y git curl wget python3 python3-pip python3-venv
```

### 步骤2: 下载代码
```bash
# 克隆项目
git clone https://github.com/T-DWAG/yak_v2.git
cd yak_v2

# 设置权限
chmod +x *.sh
```

### 步骤3: 环境配置
```bash
# 创建Python虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install flask==3.0.0 pillow>=10.0.0 imagehash>=4.3.1
```

### 步骤4: 启动服务
```bash
# 快速启动
./start-linux.sh

# 或手动启动
export PYTHONPATH=$(pwd)/src
python3 run.py
```

## 🔑 甲方体验测试流程

### 第1步: 启动系统
```bash
# 任选一种启动方式
./ubuntu-deploy.sh  # 一键部署
# 或
./start-linux.sh    # 快速启动
# 或
docker-compose -f docker-compose.ubuntu.yml up -d  # Docker方式
```

### 第2步: 访问Web界面
- 本机访问: http://localhost:5000
- 远程访问: http://服务器IP:5000
- 显示"需要授权"界面

### 第3步: 生成客户端钥匙
```bash
# 激活虚拟环境（如果使用python方式）
source venv/bin/activate

# 生成客户端钥匙
python3 tools/client_key_generator.py

# 查看生成的钥匙
cat client_key.json
```

### 第4步: 生成授权钥匙（模拟乙方）
```bash
# 生成授权钥匙
python3 tools/provider_key_generator.py client_key.json

# 查看授权内容
cat provider_key.json
```

### 第5步: Web界面授权测试
1. 在Web界面点击"浏览"，选择provider_key.json
2. 点击"上传授权钥匙"
3. 系统显示：
   - ✅ 授权验证成功
   - 配额：5000张图片
   - 剩余：5000张
   - 有效期：30天
   - IP限制：当前IP

### 第6步: 功能测试
1. **正常使用**: 上传牦牛图片ZIP文件，查看相似度分析结果
2. **配额限制**: 查看使用量统计和剩余配额
3. **防篡改测试**:
   ```bash
   # 修改授权文件配额
   sed -i 's/"total_images_allowed": 5000/"total_images_allowed": 50000/' provider_key.json
   
   # 重新上传，应该看到防篡改错误
   ```

## 🔧 系统服务管理

### 使用systemd（一键部署会自动配置）
```bash
# 启动服务
sudo systemctl start yak-analyzer

# 停止服务
sudo systemctl stop yak-analyzer

# 重启服务
sudo systemctl restart yak-analyzer

# 查看状态
sudo systemctl status yak-analyzer

# 查看日志
sudo journalctl -u yak-analyzer -f

# 开机自启
sudo systemctl enable yak-analyzer
```

## 🚨 故障排除

### 端口占用
```bash
# 检查端口占用
sudo netstat -tulnp | grep :5000

# 杀死占用进程
sudo fuser -k 5000/tcp
```

### 权限问题
```bash
# 修复权限
chmod +x ubuntu-deploy.sh start-linux.sh
chown -R $USER:$USER ~/yak-analyzer
```

### Python环境问题
```bash
# 检查Python版本
python3 --version  # 需要3.9+

# 重建虚拟环境
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install flask pillow imagehash
```

### Docker问题
```bash
# 检查Docker状态
sudo systemctl status docker

# 清理Docker缓存
docker system prune -f

# 查看容器日志
docker logs -f container_name
```

## 🔒 安全配置

### 防火墙设置
```bash
# 开放5000端口
sudo ufw allow 5000/tcp

# 只允许特定IP访问
sudo ufw allow from 192.168.1.0/24 to any port 5000
```

### Nginx反向代理（可选）
```bash
# 安装Nginx
sudo apt install nginx

# 配置反向代理
sudo tee /etc/nginx/sites-available/yak-analyzer > /dev/null << 'EOF'
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

# 启用配置
sudo ln -s /etc/nginx/sites-available/yak-analyzer /etc/nginx/sites-enabled/
sudo systemctl reload nginx
```

## ✅ 测试验证

### 健康检查
```bash
# API健康检查
curl http://localhost:5000/health

# 预期返回
{"status":"healthy","timestamp":"2025-08-28T12:00:00"}
```

### 功能验证
```bash
# 检查核心模块
python3 -c "
import sys
sys.path.insert(0, 'src')
from dual_key_system import DualKeySystem
from license_manager_simple import LicenseManager
print('✅ All modules working')
"
```

## 📊 性能优化

### 系统优化
```bash
# 增加文件描述符限制
echo "* soft nofile 65535" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65535" | sudo tee -a /etc/security/limits.conf

# 优化内核参数
echo "net.core.somaxconn = 65535" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### 应用优化
- 使用Nginx反向代理
- 配置SSL证书（Let's Encrypt）
- 启用gzip压缩
- 配置静态文件缓存

---

🎉 **部署完成！** 甲方现在可以在Ubuntu服务器上完整体验双钥匙授权系统了！