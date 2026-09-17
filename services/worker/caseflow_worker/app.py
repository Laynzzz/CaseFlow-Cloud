from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST
from . import telemetry
from .runtime import Runtime
from .settings import database


@asynccontextmanager
async def lifespan(app):
    telemetry.configure()
    runtime = Runtime()
    runtime.start()
    yield
    runtime.close()
    telemetry.close()


app = FastAPI(title="CaseFlow worker operations", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/metrics")
def metrics():
    return Response(content=telemetry.render_metrics(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health():
    try:
        with database() as db:
            db.execute("SELECT 1")
        return {"status": "UP", "service": "case-worker", "database": "UP"}
    except Exception:
        return JSONResponse({"status": "DOWN", "service": "case-worker"}, status_code=503)
