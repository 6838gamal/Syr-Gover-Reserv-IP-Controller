import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .alerts import AlertManager
from .config import get_settings
from .monitor import IPMonitor
from .routers import (alerts as alerts_router, ip, reserved, snapshots,
                      status, web, wireguard)
from .storage import EventStore
from .watchdog import Watchdog

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("app")

scheduler = BackgroundScheduler()


def _periodic_check():
    try:
        store = EventStore(settings.storage.db_path)
        IPMonitor(settings.monitor, store).check()
    except Exception:
        log.exception("periodic ip check failed")


def _periodic_watchdog():
    try:
        wd = Watchdog(
            settings.watchdog.heartbeat_file,
            settings.watchdog.stale_after_seconds,
            AlertManager(settings.alerts),
        )
        wd.check_stale()
    except Exception:
        log.exception("watchdog check failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # heartbeat أولي
    try:
        wd = Watchdog(
            settings.watchdog.heartbeat_file,
            settings.watchdog.stale_after_seconds,
            AlertManager(settings.alerts),
        )
        wd.beat()
    except Exception:
        log.exception("initial heartbeat failed")

    # جدولة
    if not scheduler.running:
        scheduler.add_job(_periodic_check, "interval", minutes=5,
                          id="ip_check")
        scheduler.add_job(
            _periodic_watchdog, "interval",
            seconds=settings.watchdog.check_interval_seconds,
            id="watchdog_check",
        )
        scheduler.start()
        log.info("Scheduler بدأ")

    yield

    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="DO + WireGuard Manager",
    version=__version__,
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)


@app.middleware("http")
async def heartbeat_middleware(request, call_next):
    # heartbeat عند كل طلب (خفيف)
    try:
        wd = Watchdog(
            settings.watchdog.heartbeat_file,
            settings.watchdog.stale_after_seconds,
            AlertManager(settings.alerts),
        )
        wd.beat()
    except Exception:
        pass
    return await call_next(request)


STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# API
app.include_router(status.router)
app.include_router(ip.router)
app.include_router(snapshots.router)
app.include_router(reserved.router)
app.include_router(wireguard.router)
app.include_router(alerts_router.router)

# Web
app.include_router(web.router)


@app.get("/health", tags=["meta"])
def health():
    return {"ok": True, "version": __version__}


@app.exception_handler(Exception)
async def unhandled(request, exc):
    log.exception("Unhandled: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "خطأ داخلي", "type": exc.__class__.__name__},
    )
