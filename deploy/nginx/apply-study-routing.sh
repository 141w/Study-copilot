set -e
cd /opt/study-copilot
sed -i "s#^APP_BIND=.*#APP_BIND=127.0.0.1#" .env
grep -E "^(APP_BIND|APP_HOST_PORT)" .env
docker compose up -d app >/dev/null 2>&1
sleep 8
echo "--- 应用监听（应为 127.0.0.1:8080）---"
ss -ltn | grep 8080 || echo "8080 未监听"
cp /tmp/study.conf /etc/nginx/sites-available/study
ln -sfn /etc/nginx/sites-available/study /etc/nginx/sites-enabled/study
nginx -t 2>&1 | tail -2
systemctl reload nginx
echo "--- 按域名分流验证 ---"
echo -n "study 域名 /health -> "
curl -s -m 10 -H "Host: study.wweiqi.devs.surf" http://127.0.0.1/health
echo
echo -n "个人站域名 -> HTTP "
curl -s -o /dev/null -w "%{http_code}\n" -m 10 -H "Host: wweiqi.devs.surf" http://127.0.0.1/
echo "（8080 是否仍对公网开放，需从服务器外部探测，见脚本外的公网检查）"
