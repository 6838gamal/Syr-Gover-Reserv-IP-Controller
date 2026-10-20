from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..alerts import AlertManager
from ..config import Settings, get_settings
from ..deps import get_alerts, get_do, get_store, get_wg
from ..do_client import DOClient
from ..monitor import IPMonitor
from ..snapshot import SnapshotManager
from ..storage import EventStore
from ..wireguard import WireGuard

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


# ---------- Pages ----------
@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/snapshots-page", response_class=HTMLResponse)
def snapshots_page(request: Request):
    return templates.TemplateResponse("snapshots.html", {"request": request})


@router.get("/events-page", response_class=HTMLResponse)
def events_page(request: Request):
    return templates.TemplateResponse("events.html", {"request": request})


@router.get("/alerts-page", response_class=HTMLResponse)
def alerts_page(
    request: Request,
    settings: Settings = Depends(get_settings),
    alerts: AlertManager = Depends(get_alerts),
):
    return templates.TemplateResponse(
        "alerts.html",
        {"request": request, "settings": settings,
         "channels": len(alerts.channels)},
    )


# ---------- Helpers ----------
def _status_data(settings: Settings, do: DOClient, wg: WireGuard) -> dict:
    droplet = do.get_droplet(settings.droplet.id)
    reserved = [r for r in do.list_reserved_ips()
                if r.get("droplet", {}).get("id") == settings.droplet.id]
    return {
        "droplet_id": settings.droplet.id,
        "droplet_status": droplet["status"],
        "public_ip": do.get_public_ip(settings.droplet.id),
        "reserved_ip": reserved[0]["ip"] if reserved else None,
        "wireguard_active": wg.is_active(),
        "checked_at": datetime.now(timezone.utc),
    }


def _deep_health(settings: Settings, do: DOClient, wg: WireGuard) -> dict:
    checks: dict[str, bool] = {}
    issues: list[str] = []

    checks["wireguard_active"] = wg.is_active()
    if not checks["wireguard_active"]:
        issues.append("WireGuard متوقف")

    try:
        reserved = [r for r in do.list_reserved_ips()
                    if r.get("droplet", {}).get("id") == settings.droplet.id]
    except Exception:
        reserved = []
    checks["reserved_ip_bound"] = bool(reserved)
    if not checks["reserved_ip_bound"]:
        issues.append("لا يوجد Reserved IP مربوط")

    if reserved:
        try:
            public_ip = do.get_public_ip(settings.droplet.id)
        except Exception:
            public_ip = None
        checks["public_ip_matches"] = public_ip == reserved[0]["ip"]
        if not checks["public_ip_matches"]:
            issues.append(f"IP العام ≠ Reserved")

    try:
        snaps = do.list_snapshots(
            prefix=f"{settings.snapshot.name_prefix}-{settings.droplet.id}"
        )
        checks["has_snapshot"] = bool(snaps)
        if not snaps:
            issues.append("لا يوجد snapshots")
    except Exception:
        checks["has_snapshot"] = False

    return {"ok": not issues, "checks": checks, "issues": issues}


# ---------- HTMX partials ----------
@router.get("/partials/status", response_class=HTMLResponse)
def partial_status(
    request: Request,
    settings: Settings = Depends(get_settings),
    do: DOClient = Depends(get_do),
    wg: WireGuard = Depends(get_wg),
):
    return templates.TemplateResponse(
        "partials/status_card.html",
        {"request": request, "s": _status_data(settings, do, wg)},
    )


@router.get("/partials/health", response_class=HTMLResponse)
def partial_health(
    request: Request,
    settings: Settings = Depends(get_settings),
    do: DOClient = Depends(get_do),
    wg: WireGuard = Depends(get_wg),
):
    return templates.TemplateResponse(
        "partials/health_card.html",
        {"request": request, "h": _deep_health(settings, do, wg)},
    )


@router.get("/partials/ip", response_class=HTMLResponse)
def partial_ip(
    request: Request,
    settings: Settings = Depends(get_settings),
    store: EventStore = Depends(get_store),
):
    result = IPMonitor(settings.monitor, store).check()
    return templates.TemplateResponse(
        "partials/ip_card.html", {"request": request, "result": result}
    )


@router.post("/ui/ip/check", response_class=HTMLResponse)
def ui_check_ip(
    request: Request,
    settings: Settings = Depends(get_settings),
    store: EventStore = Depends(get_store),
):
    result = IPMonitor(settings.monitor, store).check()
    return templates.TemplateResponse(
        "partials/ip_card.html", {"request": request, "result": result}
    )


@router.post("/ui/wireguard/restart", response_class=HTMLResponse)
def ui_restart_wg(
    request: Request,
    settings: Settings = Depends(get_settings),
    do: DOClient = Depends(get_do),
    wg: WireGuard = Depends(get_wg),
):
    try:
        wg.restart()
    except Exception:
        pass
    return templates.TemplateResponse(
        "partials/status_card.html",
        {"request": request, "s": _status_data(settings, do, wg)},
    )


@router.post("/ui/snapshots", response_class=HTMLResponse)
def ui_create_snapshot(
    settings: Settings = Depends(get_settings),
    do: DOClient = Depends(get_do),
    store: EventStore = Depends(get_store),
):
    mgr = SnapshotManager(do, settings.droplet, settings.snapshot, store)
    try:
        res = mgr.run()
        msg = f"✅ تم إنشاء {res['name']} — حُذف القديم: {res['deleted_old']}"
        cls = "ok"
    except Exception as e:
        msg = f"❌ فشل: {e}"
        cls = "bad"
    return HTMLResponse(f'<p class="{cls}">{msg}</p>')


@router.get("/partials/snapshots", response_class=HTMLResponse)
def partial_snapshots(
    request: Request,
    settings: Settings = Depends(get_settings),
    do: DOClient = Depends(get_do),
):
    prefix = f"{settings.snapshot.name_prefix}-{settings.droplet.id}"
    return templates.TemplateResponse(
        "partials/snapshots_table.html",
        {"request": request, "snaps": do.list_snapshots(prefix=prefix)},
    )


@router.delete("/ui/snapshots/{image_id}", response_class=HTMLResponse)
def ui_delete_snapshot(
    image_id: int,
    request: Request,
    settings: Settings = Depends(get_settings),
    do: DOClient = Depends(get_do),
):
    try:
        do.delete_snapshot(image_id)
    except Exception:
        pass
    prefix = f"{settings.snapshot.name_prefix}-{settings.droplet.id}"
    return templates.TemplateResponse(
        "partials/snapshots_table.html",
        {"request": request, "snaps": do.list_snapshots(prefix=prefix)},
    )


@router.get("/partials/events", response_class=HTMLResponse)
def partial_events(
    request: Request,
    limit: int = 100,
    store: EventStore = Depends(get_store),
):
    return templates.TemplateResponse(
        "partials/events_table.html",
        {"request": request, "events": store.list_recent(limit)},
    )


@router.post("/ui/alerts/test", response_class=HTMLResponse)
def ui_test_alert(alerts: AlertManager = Depends(get_alerts)):
    if not alerts.channels:
        return HTMLResponse('<p class="bad">❌ لا قنوات مفعّلة</p>')
    alerts.channels[0].send(
        "✅ اختبار تنبيه",
        "إذا وصلتك هذه الرسالة، فالتنبيهات تعمل.",
    )
    return HTMLResponse(
        f'<p class="ok">✅ أُرسل اختبار إلى {len(alerts.channels)} قناة</p>'
    )
