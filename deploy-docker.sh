#!/bin/bash
# Study Copilot Docker 部署脚本

set -e

echo "=========================================="
echo "  Study Copilot Docker 部署"
echo "=========================================="
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装"
    echo "请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose 未安装"
    exit 1
fi

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "⚠️  .env 文件不存在，从模板创建..."
    cp .env.example .env
    echo "请编辑 .env 文件，填入你的 API Key"
    echo ""
fi

# 构建并启动
echo "🚀 构建并启动服务..."
echo ""

docker-compose up -d --build

echo ""
echo "=========================================="
echo "  部署完成!"
echo "=========================================="
echo ""
echo "访问地址："
echo "  - 前端: http://localhost:3000"
echo "  - 后端 API: http://localhost:8000"
echo "  - API 文档: http://localhost:8000/docs"
echo ""
echo "常用命令："
echo "  - 查看日志: docker-compose logs -f"
echo "  - 停止服务: docker-compose down"
echo "  - 重启服务: docker-compose restart"
echo ""
