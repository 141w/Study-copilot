# API Key 加密密钥轮转手册

适用于 Study Copilot 自托管部署（Fernet / MultiFernet）。

## 密钥来源优先级

1. `ENCRYPTION_KEY_FILE`（推荐，Docker/K8s Secret 挂载文件）
2. `ENCRYPTION_KEY`（环境变量，兼容旧部署）
3. `ENCRYPTION_FALLBACK_KEYS`（逗号分隔历史密钥，**仅用于解密**）

## 轮转步骤（在线，无需停机）

1. 生成新主密钥：
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
2. 将**旧主密钥**追加到 `ENCRYPTION_FALLBACK_KEYS`（若已有多个用逗号连接）。
3. 将**新密钥**写入 `ENCRYPTION_KEY_FILE`（或替换 `ENCRYPTION_KEY`）。
4. 滚动重启应用进程。新写入的密文使用新钥；旧密文仍可解密。
5. 执行存量重加密（可选脚本思路）：
   ```python
   from app.core.encryption import get_encryption_service
   svc = get_encryption_service()
   # 对 user_llm_configs.api_key 等字段：svc.rotate(old_cipher) 后写回
   ```
6. 观察至少一个完整业务周期无解密失败后，从 `ENCRYPTION_FALLBACK_KEYS` 移除最旧密钥。

## 泄露应急

1. 立即轮换主密钥（新钥 + 旧钥进 fallback）。
2. 强制用户重新保存各 Provider API Key（清空或标记 `api_key` 需刷新）。
3. 审计访问日志中加密配置读取路径。
4. 评估是否需要在上游 Provider 侧吊销已暴露 Key。

## 不要做的事

- 不要把主密钥提交进 Git。
- 不要在多环境共用同一把生产密钥。
- 不要在未配置 fallback 时直接删掉旧钥（会导致历史密文无法解密）。
