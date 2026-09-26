set -e
cd /opt/study-copilot
git fetch -q origin master && git merge --ff-only -q origin/master
echo "代码版本: $(git log --oneline -1)"

# --- 应用侧：声明挂在 /study/ 下 ---
if grep -q "^VITE_BASE" .env; then
  sed -i "s#^VITE_BASE=.*#VITE_BASE=/study/#" .env
else
  printf "VITE_BASE=/study/\n" >> .env
fi
grep "^VITE_BASE" .env

# --- nginx：撤掉子域方案，改用子路径 ---
rm -f /etc/nginx/sites-enabled/study
STAMP=$(date +%Y%m%d-%H%M)
cp /etc/nginx/snippets/ww-common.conf "/etc/nginx/snippets/ww-common.conf.bak-$STAMP"
echo "个人站配置备份: ww-common.conf.bak-$STAMP"

cp deploy/nginx/study-subpath.conf /etc/nginx/snippets/study-subpath.conf
if ! grep -q "study-subpath" /etc/nginx/snippets/ww-common.conf; then
  # 插到通用 location / 之前，保证 /study/ 优先匹配
  sed -i '0,/^location \/ {/s|^location / {|include /etc/nginx/snippets/study-subpath.conf;\n\nlocation / {|' /etc/nginx/snippets/ww-common.conf
fi
echo "--- 修改后的个人站片段 ---"
grep -n "include /etc/nginx/snippets/study-subpath" /etc/nginx/snippets/ww-common.conf

nginx -t
systemctl reload nginx
echo "nginx 已重载"

# --- 重建应用镜像（前端要带 /study/ 基址） ---
docker compose build app 2>&1 | tail -2
docker compose up -d app 2>&1 | tail -1
sleep 25
docker ps --format "{{.Names}} {{.Status}}"
