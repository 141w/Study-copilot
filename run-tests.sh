#!/bin/bash
# Study Copilot 测试脚本

set -e

echo "=========================================="
echo "  Study Copilot 测试套件"
echo "=========================================="
echo ""

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 检查 pytest
if ! python3 -m pytest --version &> /dev/null; then
    echo "📦 安装 pytest..."
    pip install pytest pytest-asyncio httpx
fi

# 进入后端目录
cd "$(dirname "$0")/backend"

echo "🧪 运行测试..."
echo ""

# 运行测试
python3 -m pytest tests/ -v --tb=short

echo ""
echo "=========================================="
echo "  测试完成!"
echo "=========================================="
