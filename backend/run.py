import os
import sys

# 绕过 VPN 透明代理
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

import uvicorn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
