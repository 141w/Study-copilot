#!/usr/bin/env bash
# 一键部署 / 回滚 —— 在服务器上执行：bash deploy/deploy.sh
#
# 做什么：拉代码 → 重建应用镜像 → 重启容器 → 探活；探活失败自动回滚到
# 部署前那个镜像并退出非零。数据库结构不用管：容器入口会自动引导/升级。
#
# 已知边界（重要）：回滚只回滚**镜像**。如果新版本已经执行了数据库迁移，
# 回滚后的旧代码可能不认识新结构。因此带迁移的版本要格外小心：
# 先备份，再部署。备份不在本脚本职责内。

set -euo pipefail
cd "$(dirname "$0")/.."

APP_IMAGE="study-copilot-app:latest"
HEALTH_PROBES=20      # 探活次数
HEALTH_INTERVAL=3     # 每次间隔秒数

log() { printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

probe() {
  # 走容器内的 nginx（80），这样连"健康检查路径是否被正确代理"一起验了
  docker compose exec -T app curl -sf -m 8 http://127.0.0.1/health >/dev/null 2>&1
}

wait_healthy() {
  local i
  for i in $(seq 1 "$HEALTH_PROBES"); do
    if probe; then return 0; fi
    sleep "$HEALTH_INTERVAL"
  done
  return 1
}

# --- 0. 记录回滚锚点 ---
PREV_ID=$(docker image inspect --format '{{.Id}}' "$APP_IMAGE" 2>/dev/null || echo "")
log "部署前镜像: ${PREV_ID:-（无，首次部署）}"
GIT_OLD=$(git rev-parse --short HEAD)

# --- 1. 拉代码（GitHub 从国内偶发抖动，重试三次）---
log "拉取代码…"
ok=0
for i in 1 2 3; do
  if git fetch origin master && git merge --ff-only -q origin/master; then ok=1; break; fi
  log "第 $i 次拉取失败，5 秒后重试"
  sleep 5
done
[ "$ok" = 1 ] || { log "❌ 拉取失败，中止（未改动任何运行中的东西）"; exit 1; }
GIT_NEW=$(git rev-parse --short HEAD)
log "代码 $GIT_OLD → $GIT_NEW"

# --- 2. 重建镜像 ---
log "重建应用镜像（依赖层有缓存时约 1-2 分钟）…"
docker compose build app

# --- 3. 起新容器 ---
log "启动新版本…"
docker compose up -d app

# --- 4. 探活，失败即回滚 ---
if wait_healthy; then
  log "✅ 新版本健康检查通过"
else
  log "❌ 新版本探活失败，开始回滚"
  docker compose logs --tail=25 app || true
  if [ -n "$PREV_ID" ]; then
    docker tag "$PREV_ID" "$APP_IMAGE"
    docker compose up -d --no-build app
    if wait_healthy; then
      log "↩️  已回滚到 ${PREV_ID:0:12}，请排查后再部署"
    else
      log "🚨 回滚后仍不健康，需要人工介入（代码版本 $GIT_NEW）"
    fi
  else
    log "🚨 没有可回滚的旧镜像，需要人工介入"
  fi
  exit 1
fi

# --- 5. 收尾信息 ---
log "当前状态"
docker ps --format '  {{.Names}}  {{.Status}}'
docker images --format '  {{.Repository}}:{{.Tag}}  {{.Size}}  {{.ID}}' | grep study-copilot || true
free -m | awk 'NR==2{printf "  内存 %s/%sMB\n", $3, $2} NR==3{printf "  交换 %s/%sMB\n", $3, $2}'
df -h / | awk 'NR==2{printf "  磁盘 %s/%s (%s)\n", $3, $2, $5}'
log "完成：$GIT_NEW"
