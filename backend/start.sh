#!/bin/bash
# Study Copilot 后端启动脚本
cd "$(dirname "$0")"

# 防止 HuggingFace 联网下载模型
export HF_HUB_OFFLINE=1

# 绕过 VPN 透明代理（iKuuuVPN 会劫持 httpx 请求到 localhost:12000）
export NO_PROXY="*"
export no_proxy="*"

/Users/wweiqi/miniconda3/envs/study-c/bin/python run.py
