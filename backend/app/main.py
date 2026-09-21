import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import scheduler
from .api import apikeys, auth, hosts, monitors, notify
from .db import Base, engine
from .mcp_server import mcp, mcp_asgi
from .migrate import upgrade
from .seed import seed
from .webhook import router as webhook_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

STATIC = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    upgrade()
    seed()
    scheduler.start()
    async with mcp.session_manager.run():
        yield
    scheduler.scheduler.shutdown(wait=False)


app = FastAPI(title="Service Monitor", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.include_router(auth.router)
app.include_router(monitors.router)
app.include_router(hosts.router)
app.include_router(apikeys.router)
app.include_router(notify.router)
app.include_router(webhook_router)


# MCP 通道（Streamable HTTP）：https://<host>/mcp/
app.mount("/mcp", mcp_asgi)


@app.middleware("http")
async def mcp_slash(request, call_next):
    # /mcp 與 /mcp/ 都可用，避免 client 因 307 轉址遺失 POST body
    if request.scope["path"] == "/mcp":
        request.scope["path"] = "/mcp/"
    return await call_next(request)


@app.get("/healthz")
def healthz():
    return {"ok": True}


if STATIC.exists():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = (STATIC / path).resolve()
        if path and f.is_relative_to(STATIC) and f.is_file():
            return FileResponse(f)
        return FileResponse(STATIC / "index.html")
