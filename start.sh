#!/bin/bash
# ============================================================
#  Study Copilot - macOS 一键启动脚本
#  用法: ./start.sh 或 bash start.sh
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
BACKEND_PORT=8000
FRONTEND_PORT=3000
CLASSROOM_PORT=3001
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONDA_ENV="study-c"
CONDA_BASE="$HOME/miniconda3"

# 打印函数
info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[..]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo "======================================"
echo "  Study Copilot - AI 学习助手"
echo "  macOS 一键启动"
echo "======================================"
echo ""

# ----------------------------------------------------------
# 1. 检查依赖
# ----------------------------------------------------------
info "检查依赖..."

# 检查 conda
if [ ! -f "$CONDA_BASE/bin/conda" ]; then
    error "未找到 miniconda3，请先安装: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

# 检查 conda 环境
CONDA_PYTHON="$CONDA_BASE/envs/$CONDA_ENV/bin/python"
if [ ! -f "$CONDA_PYTHON" ]; then
    error "未找到 conda 环境 '$CONDA_ENV'"
    error "请先创建: conda create -n $CONDA_ENV python=3.11"
    exit 1
fi

# 检查 node
if ! command -v node &> /dev/null; then
    error "未找到 Node.js，请先安装: brew install node"
    exit 1
fi

# 初始化 conda（非交互式 shell 需要 source）
source "$CONDA_BASE/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

# 检查后端依赖
if ! "$CONDA_PYTHON" -c "import uvicorn, fastapi, sqlalchemy, email_validator, greenlet" 2>/dev/null; then
    warn "后端依赖未安装，正在安装..."
    pip install -r "$SCRIPT_DIR/backend/requirements.txt" "pydantic[email]" -q
    ok "后端依赖安装完成"
fi

ok "依赖检查通过"

# ----------------------------------------------------------
# 1.5 预下载 AI 模型（首次启动需要）
# ----------------------------------------------------------
info "检查 AI 模型..."
"$CONDA_PYTHON" -c "
from sentence_transformers import SentenceTransformer
import os
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
try:
    m = SentenceTransformer('shibing624/text2vec-base-chinese')
    print('Embedding model OK')
except Exception as e:
    print(f'Warning: {e}')
try:
    from sentence_transformers import CrossEncoder
    m = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    print('Reranker model OK')
except Exception as e:
    print(f'Warning: {e}')
" 2>&1 | while read line; do ok "$line"; done
ok "AI 模型就绪"

# ----------------------------------------------------------
# 2. 安装前端依赖（如果需要）
# ----------------------------------------------------------
if [ ! -d "$SCRIPT_DIR/frontend/node_modules" ]; then
    warn "安装前端依赖..."
    cd "$SCRIPT_DIR/frontend"
    npm install
    if [ $? -ne 0 ]; then
        error "npm install 失败"
        exit 1
    fi
    cd "$SCRIPT_DIR"
    ok "前端依赖安装完成"
else
    # 修复 node_modules/.bin 权限问题
    chmod +x "$SCRIPT_DIR/frontend/node_modules/.bin/"* 2>/dev/null || true
    ok "前端依赖已就绪"
fi

# ----------------------------------------------------------
# 3. 检查并释放端口
# ----------------------------------------------------------
info "检查端口..."

# 确保 PostgreSQL 正在运行
if ! pg_isready -q 2>/dev/null; then
    warn "PostgreSQL 未运行，正在启动..."
    brew services start postgresql@16 2>/dev/null || true
    sleep 2
fi
ok "PostgreSQL 就绪"

kill_port() {
    local port=$1
    local pid=$(lsof -ti :$port 2>/dev/null)
    if [ -n "$pid" ]; then
        warn "端口 $port 被占用 (PID: $pid)，正在释放..."
        kill -9 $pid 2>/dev/null || true
        sleep 1
    fi
}

kill_port $BACKEND_PORT
kill_port $FRONTEND_PORT
kill_port $CLASSROOM_PORT
ok "端口检查完成"

# ----------------------------------------------------------
# 4. 启动后端
# ----------------------------------------------------------
info "启动后端 (端口 $BACKEND_PORT)..."

# 设置 HuggingFace 离线模式（使用本地缓存的模型）
export HF_HUB_OFFLINE=1

# 后台启动 FastAPI
cd "$SCRIPT_DIR/backend"
nohup "$CONDA_PYTHON" run.py > /tmp/study-copilot-backend.log 2>&1 &
BACKEND_PID=$!
cd "$SCRIPT_DIR"

# 等待后端就绪
warn "等待后端启动..."
RETRIES=0
MAX_RETRIES=20
while [ $RETRIES -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:$BACKEND_PORT/health > /dev/null 2>&1; then
        ok "后端已就绪 (PID: $BACKEND_PID)"
        break
    fi
    sleep 1
    RETRIES=$((RETRIES + 1))
    if [ $RETRIES -ge $MAX_RETRIES ]; then
        error "后端启动超时，请检查日志: /tmp/study-copilot-backend.log"
        exit 1
    fi
done

# ----------------------------------------------------------
# 5. 启动前端
# ----------------------------------------------------------
info "启动前端 (端口 $FRONTEND_PORT)..."

cd "$SCRIPT_DIR/frontend"
nohup npm run dev -- --port $FRONTEND_PORT > /tmp/study-copilot-frontend.log 2>&1 &
FRONTEND_PID=$!
cd "$SCRIPT_DIR"

# 等待前端就绪
warn "等待前端启动..."
RETRIES=0
while [ $RETRIES -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
        ok "前端已就绪 (PID: $FRONTEND_PID)"
        break
    fi
    sleep 1
    RETRIES=$((RETRIES + 1))
    if [ $RETRIES -ge $MAX_RETRIES ]; then
        error "前端启动超时，请检查日志: /tmp/study-copilot-frontend.log"
        exit 1
    fi
done

# ----------------------------------------------------------
# 5.5 启动 AI 互动课堂引擎（可选微服务，端口 $CLASSROOM_PORT）
# ----------------------------------------------------------
CLASSROOM_PID=""
if [ -d "$SCRIPT_DIR/classroom/node_modules" ]; then
    info "启动 AI 互动课堂引擎 (端口 $CLASSROOM_PORT)..."
    cd "$SCRIPT_DIR/classroom"
    nohup npx pnpm dev -p $CLASSROOM_PORT > /tmp/study-copilot-classroom.log 2>&1 &
    CLASSROOM_PID=$!
    cd "$SCRIPT_DIR"
    ok "AI 互动课堂引擎已在后台启动 (PID: $CLASSROOM_PID)"
else
    info "AI 互动课堂引擎：已启用后端原生大纲与测验智能生成保底模式。"
    info "（如需全功能互动课件渲染，可随时进入 classroom/ 执行 npx pnpm install && npx pnpm dev -p $CLASSROOM_PORT）"
fi

# ----------------------------------------------------------
# 6. 打开浏览器
# ----------------------------------------------------------
echo ""
echo "======================================"
echo -e "  ${GREEN}所有服务已启动！${NC}"
echo ""
echo "  前端: http://localhost:$FRONTEND_PORT"
echo "  后端: http://localhost:$BACKEND_PORT/docs"
if [ -n "$CLASSROOM_PID" ]; then
    echo "  课堂: http://localhost:$CLASSROOM_PORT"
fi
echo ""
echo "  后端日志: /tmp/study-copilot-backend.log"
echo "  前端日志: /tmp/study-copilot-frontend.log"
if [ -n "$CLASSROOM_PID" ]; then
    echo "  课堂日志: /tmp/study-copilot-classroom.log"
fi
echo ""
echo "  停止服务: ./stop.sh 或 Ctrl+C"
echo "======================================"
echo ""

open "http://localhost:$FRONTEND_PORT"

# 等待用户 Ctrl+C 停止
cleanup() {
    echo ""
    warn "正在停止服务..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    if [ -n "$CLASSROOM_PID" ]; then
        kill $CLASSROOM_PID 2>/dev/null || true
    fi
    # 清理残留进程
    kill_port $BACKEND_PORT
    kill_port $FRONTEND_PORT
    kill_port $CLASSROOM_PORT
    ok "服务已停止"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "按 Ctrl+C 停止所有服务..."
wait
