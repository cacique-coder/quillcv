import os

APP_ENV = os.environ.get("APP_ENV", "development")

DATABASE = {
    "development": {
        "url": "postgresql+asyncpg://postgres:postgres@localhost:5432/quillcv_dev",
        "echo": True,
        "pool_size": 5,
    },
    "test": {
        "url": "postgresql+asyncpg://postgres:postgres@localhost:5432/quillcv_test",
        "echo": False,
        "pool_size": 5,
    },
    "production": {
        "url": os.environ.get("DATABASE_URL"),
        "echo": False,
        "pool_size": 10,
    },
}


def database_config():
    """Return database config for current environment.

    DATABASE_URL env var always takes precedence (like Rails).
    """
    config = DATABASE[APP_ENV].copy()
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        config["url"] = env_url
    return config
