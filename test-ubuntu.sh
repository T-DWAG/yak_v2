#!/bin/bash
# Ubuntu环境完整测试脚本

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=============================================="
echo -e "🧪 Ubuntu环境完整测试脚本"
echo -e "=============================================="${NC}

# 测试函数
run_test() {
    local test_name="$1"
    local command="$2"
    
    echo -e "${YELLOW}[测试] $test_name${NC}"
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ $test_name - 通过${NC}"
        return 0
    else
        echo -e "${RED}❌ $test_name - 失败${NC}"
        return 1
    fi
}

# 计数器
passed=0
failed=0

# 测试1: Python环境
if run_test "Python 3.9+ 版本检查" 'python3 --version | grep -E "Python 3\.(9|10|11|12)"'; then
    ((passed++))
else
    ((failed++))
fi

# 测试2: 依赖包
if run_test "Flask包安装检查" 'python3 -c "import flask; print(flask.__version__)"'; then
    ((passed++))
else
    echo -e "${YELLOW}尝试安装Flask...${NC}"
    if pip3 install flask pillow imagehash --quiet; then
        ((passed++))
        echo -e "${GREEN}✅ 依赖包安装成功${NC}"
    else
        ((failed++))
    fi
fi

# 测试3: 核心模块导入
export PYTHONPATH="$(pwd)/src"
if run_test "核心模块导入" 'python3 -c "
import sys
sys.path.insert(0, \"src\")
from dual_key_system import DualKeySystem
from license_manager_simple import LicenseManager
import group3
"'; then
    ((passed++))
else
    ((failed++))
fi

# 测试4: Mock YOLO系统
if run_test "Mock YOLO系统" 'python3 -c "
import sys
sys.path.insert(0, \"src\")
import group3
model = group3.load_yolo_model()
print(\"Mock YOLO working\")
"'; then
    ((passed++))
else
    ((failed++))
fi

# 测试5: 双钥匙系统
if run_test "双钥匙系统功能" 'python3 -c "
import sys, json
sys.path.insert(0, \"src\")
from dual_key_system import DualKeySystem
dual_key = DualKeySystem()
client_data = {\"client_id\": \"test\", \"images_used\": 100}
auth_params = {\"total_images_allowed\": 5000, \"valid_until\": \"2025-12-31T23:59:59\"}
success, key = dual_key.generate_provider_key(json.dumps(client_data), auth_params)
assert success, \"Provider key generation failed\"
"'; then
    ((passed++))
else
    ((failed++))
fi

# 测试6: Web应用启动（快速测试）
echo -e "${YELLOW}[测试] Web应用启动测试${NC}"
python3 run.py &
APP_PID=$!
sleep 3

if curl -f http://localhost:5000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Web应用启动 - 通过${NC}"
    ((passed++))
else
    echo -e "${RED}❌ Web应用启动 - 失败${NC}"
    ((failed++))
fi

# 清理
kill $APP_PID 2>/dev/null || true

# 测试7: 工具脚本
if run_test "客户端钥匙生成工具" 'python3 tools/client_key_generator.py --test'; then
    ((passed++))
else
    ((failed++))
fi

# 测试8: 文件权限
if run_test "脚本文件权限" 'test -x ubuntu-deploy.sh && test -x start-linux.sh'; then
    ((passed++))
else
    chmod +x *.sh
    ((passed++))
    echo -e "${GREEN}✅ 文件权限已修复${NC}"
fi

# 测试结果
echo -e "${BLUE}=============================================="
echo -e "📊 测试结果统计"
echo -e "=============================================="${NC}
echo -e "${GREEN}通过: $passed${NC}"
echo -e "${RED}失败: $failed${NC}"
echo -e "总计: $((passed + failed))"

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}🎉 所有测试通过！Ubuntu部署环境完全就绪！${NC}"
    echo
    echo -e "${BLUE}📋 接下来的操作:${NC}"
    echo "1. 启动系统: ./start-linux.sh"
    echo "2. 访问Web界面: http://localhost:5000"
    echo "3. 生成客户端钥匙: python3 tools/client_key_generator.py"
    echo "4. 生成授权钥匙: python3 tools/provider_key_generator.py client_key.json"
    echo
    exit 0
else
    echo -e "${RED}⚠️  有 $failed 个测试失败，请检查环境配置${NC}"
    echo
    echo -e "${YELLOW}常见解决方法:${NC}"
    echo "1. 安装Python 3.9+: sudo apt install python3 python3-pip python3-venv"
    echo "2. 安装依赖: pip3 install flask pillow imagehash"
    echo "3. 检查权限: chmod +x *.sh"
    echo "4. 检查端口: sudo netstat -tulnp | grep :5000"
    echo
    exit 1
fi