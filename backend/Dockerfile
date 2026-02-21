# 使用国内镜像源加速基础镜像下载 (由 docker.io/library/python:3.12-slim 替换)
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/python:3.12-slim

WORKDIR /app

# 1. 优化：配置国内镜像源 (清华源)
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources \
    && pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Copy requirements
COPY backend/requirements.txt /app/backend/requirements.txt

# 2. 安装 Python 依赖
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 3. 安装 Chromium 浏览器 (仅下载二进制文件)
RUN playwright install chromium

# 4. 手动安装系统依赖 (Debian 12 专用)
# 修复 playwright install-deps 在 Debian Slim 下因包名不匹配报错的问题
RUN apt-get update && apt-get install -y --no-install-recommends \
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
    && rm -rf /var/lib/apt/lists/*

# Copy backend code
COPY backend /app/backend
COPY frontend /app/frontend

# Set PYTHONPATH
ENV PYTHONPATH=/app/backend

# Expose port
EXPOSE 8000

# Default command
CMD ["python", "backend/reporting/dashboard_server.py"]
