import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from starlette.middleware.sessions import SessionMiddleware

from app.routers import cv, demo, photos, wizard
from app.routers import auth as auth_router
from app.routers import payments as payments_router
from app.routers import landing as landing_router
from app.services.llm_client import AnthropicAPIClient, ClaudeCodeClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import init_db
    await init_db()
    yield


app = FastAPI(title="QuillCV", lifespan=lifespan)

# Dev mode: enabled when using the default session secret (i.e. local development)
app.state.dev_mode = os.environ.get("SESSION_SECRET", "quillcv-dev-secret-change-in-prod") == "quillcv-dev-secret-change-in-prod"

# Session middleware for attempt tracking
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "quillcv-dev-secret-change-in-prod"),
)

# LLM clients: primary (Sonnet) for CV generation, fast (Haiku) for lightweight tasks
if os.environ.get("ANTHROPIC_API_KEY"):
    app.state.llm = AnthropicAPIClient(model="claude-sonnet-4-20250514")
    app.state.llm_fast = AnthropicAPIClient(model="claude-haiku-4-5-20251001")
else:
    app.state.llm = ClaudeCodeClient(model="sonnet")
    app.state.llm_fast = ClaudeCodeClient(model="haiku")

app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)

# Auth & payments
app.include_router(auth_router.router)
app.include_router(payments_router.router)

# Landing page replaces the old / route
app.include_router(landing_router.router)

# App routes
app.include_router(wizard.router)
app.include_router(cv.router)
app.include_router(demo.router)
app.include_router(photos.router)


