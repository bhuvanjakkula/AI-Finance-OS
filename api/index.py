"""Vercel Python ASGI entrypoint serving the FastAPI backend under /api/*."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("FINANCE_AUTO_CREATE", "true")
os.environ.setdefault("FINANCE_ALLOWED_HOSTS", "*")
os.environ.setdefault("CORS_ORIGINS", "*")
os.environ.setdefault("ALLOW_REGISTRATION", "true")

from app.database import Base, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.pqc_security import keys as security_keys  # noqa: E402

Base.metadata.create_all(engine)
security_keys()


async def app(scope, receive, send):
    if scope["type"] in ("http", "websocket"):
        path = scope.get("path", "")
        if path == "/api":
            scope = {**scope, "path": "/"}
        elif path.startswith("/api/"):
            scope = {**scope, "path": path[4:]}
    await fastapi_app(scope, receive, send)
