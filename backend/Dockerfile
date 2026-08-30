# ---- Frontend Builder ----
FROM docker.m.daocloud.io/library/node:20-alpine AS frontend-builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---- Backend Builder ----
FROM docker.m.daocloud.io/library/python:3.11-slim AS backend-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_DEFAULT_TIMEOUT=120

COPY pyproject.toml ./
COPY app/ ./app/

RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir uv
RUN uv pip install --system --prefix=/install . --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match

RUN mkdir -p /opt/hf

# ---- Runtime ----
FROM docker.m.daocloud.io/library/python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    libpq-dev \
    curl \
    util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# Backend deps from build stage
COPY --from=backend-builder /install /usr/local
COPY --from=backend-builder /opt/hf /opt/hf
ENV HF_HOME=/opt/hf

# Frontend from build stage
COPY --from=frontend-builder /app/dist /usr/share/nginx/html/

# Nginx config (proxy to localhost:8000)
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Backend code
COPY backend/app/ ./app/
COPY backend/alembic/ ./alembic/
COPY backend/alembic.ini ./
COPY backend/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh && \
    chown -R www-data:www-data /usr/share/nginx/html && \
    useradd -r -u 1000 -g www-data appuser && \
    chown -R appuser:www-data /app && \
    mkdir -p /app/uploads /app/vectorstore /app/.embedding_cache

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
