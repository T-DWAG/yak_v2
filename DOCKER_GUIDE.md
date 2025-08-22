# 🐳 Docker部署指南

## 快速开始

### 方法1：使用Docker Compose（推荐）
```bash
# 克隆项目
git clone https://github.com/T-DWAG/yak_v2.git
cd yak_v2

# 启动服务
docker-compose up --build

# 访问系统
# http://localhost:5000
```

### 方法2：使用Docker直接运行
```bash
# 构建镜像
docker build -t yak-analyzer .

# 运行容器
docker run -d \
  --name yak-analyzer \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/results:/app/results \
  yak-analyzer
```

## 甲方体验测试流程

### 第1步：启动系统
```bash
docker-compose up --build
```
系统会启动在 http://localhost:5000

### 第2步：甲方首次使用（生成客户端钥匙）
```bash
# 进入容器
docker exec -it yak_v2_yak-analyzer_1 bash

# 生成客户端钥匙
python tools/client_key_generator.py

# 查看生成的钥匙
cat client_key.json
```

### 第3步：乙方生成授权钥匙
```bash
# 在容器内
python tools/provider_key_generator.py client_key.json

# 查看授权钥匙
cat provider_key.json
```

### 第4步：甲方使用授权
- 将provider_key.json上传到Web界面的"授权管理"区域
- 系统会验证授权并显示配额信息
- 现在可以正常使用图片分析功能

### 第5步：测试防篡改功能
```bash
# 在容器内修改授权文件
python -c "
import json
with open('provider_key.json', 'r') as f:
    data = json.load(f)
data['total_images_allowed'] = 50000  # 篡改配额
with open('provider_key.json', 'w') as f:
    json.dump(data, f)
"

# 重新上传，应该看到防篡改错误
```

## 环境变量配置

```bash
# 自定义配置
docker run -e YOLO_MODEL_PATH=/app/data/my_model.pt \
           -e INPUT_DIR=/app/custom_uploads \
           -e OUTPUT_DIR=/app/custom_results \
           yak-analyzer
```

## 数据持久化

重要目录挂载：
- `./data:/app/data` - YOLO模型文件
- `./uploads:/app/uploads` - 上传的图片
- `./results:/app/results` - 分析结果
- `./license_data:/app/license_data` - 授权数据
- `./dual_keys:/app/dual_keys` - 钥匙文件

## 故障排除

### 容器启动失败
```bash
# 查看日志
docker-compose logs yak-analyzer

# 检查健康状态
curl http://localhost:5000/health
```

### YOLO模型不可用
- 系统会自动使用Mock实现
- 日志会显示"Using mock YOLO implementation"
- 功能正常但使用虚拟分类结果

### 权限问题
```bash
# 修复文件权限
chmod +x docker-start.sh
chmod +x docker-start.bat
```

## 生产环境部署

```bash
# 使用Nginx反向代理
docker-compose --profile production up -d

# 访问地址
# http://localhost  (通过Nginx)
# http://localhost:5000  (直接访问)
```

## 停止服务

```bash
# 停止所有服务
docker-compose down

# 清理数据卷
docker-compose down -v
```