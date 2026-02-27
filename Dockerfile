# 阶段1: 构建前端
FROM docker.m.daocloud.io/library/node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/pnpm-lock.yaml* ./
RUN npm install -g pnpm && pnpm install

COPY frontend/ ./
RUN pnpm run build

# 阶段2: 构建后端 + Nginx
FROM docker.m.daocloud.io/library/python:3.12-slim AS backend

WORKDIR /app

# 配置国内镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libglib2.0-0 \
    libgtk-3-0 \
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-arphic-uming \
    lsb-release \
    xdg-utils \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# 安装 Playwright 和 Chromium (使用系统包)
RUN pip install playwright && \
    apt-get update && apt-get install -y chromium && \
    playwright install chromium || true

# 复制 Python 依赖
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 复制后端代码
COPY backend /app/backend

# 复制前端构建产物
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/nginx.conf

# 设置环境变量
ENV PYTHONPATH=/app/backend
ENV TZ=Asia/Shanghai
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 80

# 启动 Nginx 和后端服务
CMD ["sh", "-c", "python /app/backend/reporting/dashboard_server.py & nginx -g 'daemon off;'"]
