import os
import sys

# 绕过 VPN 透明代理
os.environ.setdefault('NO_PROXY', '*')
os.environ.setdefault('no_proxy', '*')

import uvicorn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from app.config import settings
    reload_flag = os.environ.get("RELOAD", "").lower() in ("true", "1") or settings.debug
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=reload_flag)
