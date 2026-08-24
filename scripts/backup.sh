#!/usr/bin/env bash
# Study Copilot 备份脚本（自托管刚需）
# 备份内容：
#   1. PostgreSQL 数据库（pg_dump -Fc 自定义压缩格式）
#   2. uploads/   用户上传的原始文件
#   3. vectorstore/  FAISS/BM25 索引文件
#
# 用法：
#   ./scripts/backup.sh                 # 实际备份
#   DRY_RUN=1 ./scripts/backup.sh      # 只打印将执行的动作
#
# 环境变量（均可选，默认从 backend/.env 解析）：
#   BACKUP_DIR       输出目录        默认 <repo>/backups
#   BACKUP_KEEP_DAYS 保留天数        默认 14，过期自动清理
#   DATABASE_URL     覆盖 .env 中的连接串
#
# 建议 cron（每天 03:30）：
#   30 3 * * * /path/to/Study-copilot/scripts/backup.sh >> /tmp/study_backup.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$ROOT_DIR/backend/.env"

BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
DRY_RUN="${DRY_RUN:-0}"
STAMP="$(date +%Y%m%d_%H%M%S)"

log() { echo "[backup $STAMP] $*"; }

# ── 从 backend/.env 解析 DATABASE_URL（postgres:// 或 postgresql+asyncpg://）──
db_url="${DATABASE_URL:-}"
if [ -z "$db_url" ] && [ -f "$ENV_FILE" ]; then
  db_url="$(grep -E '^DATABASE_URL=' "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)"
fi

PG_ARGS=()
if [ -n "$db_url" ]; then
  clean_url="${db_url/+asyncpg/}"           # 去掉 SQLAlchemy driver 段
  clean_url="${clean_url/postgresql:/postgresql:}"
  # postgresql://user:pass@host:port/db
  cred="${clean_url#*://}"; cred="${cred%%@*}"
  hostpart="${clean_url#*@}"; hostpart="${hostpart%%/*}"
  dbname="${clean_url##*/}"; dbname="${dbname%%\?*}"
  PG_USER="${cred%%:*}"
  PG_PASS="${cred#*:}"; [ "$PG_PASS" = "$cred" ] && PG_PASS=""
  PG_HOST="${hostpart%%:*}"
  PG_PORT="${hostpart#*:}"; [ "$PG_PORT" = "$hostpart" ] && PG_PORT="5432"
  export PGPASSWORD="$PG_PASS"
  PG_ARGS=(-h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$dbname")
  log "数据库目标: $PG_USER@$PG_HOST:$PG_PORT/$dbname"
else
  PG_ARGS=()  # 走 pg_dump 默认环境（本机 socket / PGUSER 等）
  log "未解析到 DATABASE_URL，使用 pg_dump 默认连接参数"
fi

mkdir -p "$BACKUP_DIR"
run() {
  if [ "$DRY_RUN" = "1" ]; then log "DRY-RUN: $*"; else log "执行: $*"; "$@"; fi
}

# ── 1. 数据库 ──
DB_OUT="$BACKUP_DIR/db_$STAMP.dump"
if [ ${#PG_ARGS[@]} -gt 0 ]; then
  run pg_dump "${PG_ARGS[@]}" -Fc -f "$DB_OUT"
else
  run pg_dump -Fc -f "$DB_OUT"
fi

# ── 2. 文件与向量索引（实际位于 backend/ 下）──
DATA_OUT="$BACKUP_DIR/files_$STAMP.tar.gz"
cd "$ROOT_DIR/backend"
DIRS=()
[ -d uploads ] && DIRS+=(uploads)
[ -d vectorstore ] && DIRS+=(vectorstore)
if [ ${#DIRS[@]} -gt 0 ]; then
  run tar -czf "$DATA_OUT" "${DIRS[@]}"
else
  log "uploads/vectorstore 均不存在，跳过文件归档"
  DATA_OUT=""
fi

# ── 3. 过期清理 ──
if [ "$DRY_RUN" != "1" ]; then
  find "$BACKUP_DIR" -type f \( -name 'db_*.dump' -o -name 'files_*.tar.gz' \) -mtime +"$KEEP_DAYS" -print -delete |
    while read -r f; do log "清理过期: $f"; done
fi

# ── 4. 摘要 ──
log "完成。产物："
SUMMARY_FILES=("$DB_OUT")
[ -n "$DATA_OUT" ] && SUMMARY_FILES+=("$DATA_OUT")
for f in "${SUMMARY_FILES[@]}"; do
  if [ -n "$f" ] && [ -f "$f" ]; then log "  $(du -h "$f" | cut -f1)\t$f"; fi
done
