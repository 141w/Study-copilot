#!/usr/bin/env bash
# 一键部署 / 回滚 —— 在服务器上执行：bash deploy/deploy.sh
#
# 做什么：拉代码 → 重建应用镜像 → 重启容器 → 探活；探活失败自动回滚到
# 部署前那个镜像并退出非零。数据库结构不用管：容器入口会自动引导/升级。
#
# 已知边界（重要）：回滚只回滚**镜像**。如果新版本已经执行了数据库迁移，
# 回滚后的旧代码可能不认识新结构。因此带迁移的版本要格外小心：
# 先备份，再部署。本脚本会在构建前提示备份；自动备份请跑 scripts/backup.sh。

set -euo pipefail
cd "$(dirname "$0")/.."

# ── 生产专用 compose 选择 ────────────────────────────────────────────────
# 必须显式 -f，禁止依赖 docker-compose.override.yml 的自动合并。
# 历史事故：override 里 DEBUG=true + 源码挂载会被静默带上生产。
COMPOSE=(docker compose -f docker-compose.yml)

APP_IMAGE="study-copilot-app:latest"
HEALTH_PROBES=20      # 探活次数
HEALTH_INTERVAL=3     # 每次间隔秒数

log() { printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

probe() {
  # 走容器内的 nginx（80），这样连"健康检查路径是否被正确代理"一起验了
  "${COMPOSE[@]}" exec -T app curl -sf -m 8 http://127.0.0.1/health >/dev/null 2>&1
}

wait_healthy() {
  local i
  for i in $(seq 1 "$HEALTH_PROBES"); do
    if probe; then return 0; fi
    sleep "$HEALTH_INTERVAL"
  done
  return 1
}

# --- 0. 生产守卫：拒绝会被自动合并进生产的调试覆盖 ---
if [ -f docker-compose.override.yml ]; then
  log "⚠️  检测到 docker-compose.override.yml（已显式 -f 忽略，不参与本次部署）"
  log "    建议删除或改名为 docker-compose.dev.yml，避免其他命令误合并"
fi
if [ -f docker-compose.dev.yml ]; then
  # dev 文件只允许手动 -f 叠加，本脚本不会加载
  :
fi

# 生效配置里绝不能出现 DEBUG=true（防止 .env 或 override 污染）
EFFECTIVE_CFG=$("${COMPOSE[@]}" config 2>/dev/null || true)
if printf '%s' "$EFFECTIVE_CFG" | grep -q 'DEBUG: "true"\|DEBUG: true\|DEBUG=true'; then
  log "❌ 生效 compose 配置包含 DEBUG=true，拒绝部署（请检查 .env / 覆盖文件）"
  exit 1
fi

# --- 0.1 备份提示（迁移会自动跑，回滚不覆盖 DB）---
log "提示：数据库迁移会在启动时自动执行，回滚只还原镜像。"
if [ -x scripts/backup.sh ]; then
  log "      建议先执行：scripts/backup.sh（或 DRY_RUN=1 scripts/backup.sh 预览）"
fi

# --- 0.2 记录回滚锚点 ---
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

# 拉取后再验一次（新代码可能改了 compose / .env）
EFFECTIVE_CFG=$("${COMPOSE[@]}" config 2>/dev/null || true)
if printf '%s' "$EFFECTIVE_CFG" | grep -q 'DEBUG: "true"\|DEBUG: true\|DEBUG=true'; then
  log "❌ 拉取后的生效配置包含 DEBUG=true，中止（未重建镜像）"
  exit 1
fi

# --- 2. 重建镜像 ---
log "重建应用镜像（依赖层有缓存时约 1-2 分钟）…"
"${COMPOSE[@]}" build app

# --- 3. 起新容器 ---
log "启动新版本…"
"${COMPOSE[@]}" up -d app

# --- 4. 探活，失败即回滚 ---
if wait_healthy; then
  log "✅ 新版本健康检查通过"
else
  log "❌ 新版本探活失败，开始回滚"
  "${COMPOSE[@]}" logs --tail=25 app || true
  if [ -n "$PREV_ID" ]; then
    docker tag "$PREV_ID" "$APP_IMAGE"
    "${COMPOSE[@]}" up -d --no-build app
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
