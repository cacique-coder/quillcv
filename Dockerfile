# Stage 1: builder — install Python deps and Node.js packages
FROM python:3.14-slim AS builder

WORKDIR /app

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (LTS) for Puppeteer PDF generation
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into a prefix we can copy to the final stage
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Install Node dependencies
COPY package.json package-lock.json ./
RUN npm ci --omit=dev


# Stage 2: production — slim image with just what we need to run
FROM python:3.14-slim AS production

WORKDIR /app

# Runtime system dependencies: Chromium (for Puppeteer), curl (health checks), Node.js
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
    && rm -rf /var/lib/apt/lists/*

# Install Node.js runtime (needed to execute generate_pdf.js)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy installed Node modules from builder
COPY --from=builder /app/node_modules ./node_modules

# Copy application code
COPY . .

# Minify CSS for production
RUN python scripts/minify_css.py

# Non-root user for security.
# UID/GID pinned to 1000 so that a bind-mounted uploads directory on the host
# (owned by the typical deploy user, UID 1000) is writable from inside the
# container without extra chown gymnastics on the host.
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --no-create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/app/uploads \
    && chown -R appuser:appuser /app

# Declared so operators know this path holds state; the concrete bind mount
# lives in config/deploy.yml and resolves to ~deploy/storage/uploads on the host.
VOLUME ["/app/app/uploads"]

USER appuser

EXPOSE 8000

CMD ["gunicorn", "app.main:app", "-c", "gunicorn.conf.py"]
