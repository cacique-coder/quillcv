"""Gunicorn production config for QuillCV."""

import multiprocessing

# Server socket
bind = "0.0.0.0:8000"

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"

# Timeouts
timeout = 60  # WebSocket CV generation can run long
graceful_timeout = 10
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
