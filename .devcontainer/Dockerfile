# Development Dockerfile — NOT multi-stage, all tooling available
# Mirrors production runtime deps exactly (same apt packages as production stage)
FROM python:3.14-slim

WORKDIR /workspace

# System dependencies: Chromium + runtime libs (mirrors production stage exactly),
# plus git and build-essential for dev tooling
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    curl \
    fonts-liberation \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js LTS (same method as production Dockerfile)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Tell Puppeteer to use the system Chromium and skip its own download
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Node dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Dev server with hot reload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
