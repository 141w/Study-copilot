#!/bin/bash
# ============================================================
#  Study Copilot - macOS 停止脚本
#  用法: ./stop.sh
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BACKEND_PORT=8000
FRONTEND_PORT=3000

echo -e "${YELLOW}正在停止 Study Copilot 服务...${NC}"

# 按端口杀进程
for port in $BACKEND_PORT $FRONTEND_PORT; do
    pid=$(lsof -ti :$port 2>/dev/null)
    if [ -n "$pid" ]; then
        kill -9 $pid 2>/dev/null
        echo -e "${GREEN}[OK]${NC} 端口 $port 已释放 (PID: $pid)"
    else
        echo -e "${GREEN}[OK]${NC} 端口 $port 未被占用"
    fi
done

# 清理 nohup 残留
pkill -f "run.py" 2>/dev/null || true
pkill -f "vite.*--port $FRONTEND_PORT" 2>/dev/null || true

echo ""
echo -e "${GREEN}所有服务已停止${NC}"
