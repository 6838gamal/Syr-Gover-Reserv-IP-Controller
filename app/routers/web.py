from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..alerts import AlertManager
from ..config import Settings, get_settings
from ..deps import get_alerts, get_do_optional, get_store, get_wg
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
    return templates.TemplateResponse(request, "dashboard.html", {})


@router.get("/snapshots-page", response_class=HTMLResponse)
def snapshots_page(request: Request):
    return templates.TemplateResponse(request, "snapshots.html", {})


@router.get("/events-page", response_class=HTMLResponse)
def events_page(request: Request):
    return templates.TemplateResponse(request, "events.html", {})


@router.get("/alerts-page", response_class=HTMLResponse)
def alerts_page(
    request: Request,
    settings: Settings = Depends(get_settings),
    alerts: AlertManager = Depends(get_alerts),
):
    return templates.TemplateResponse(
        request,
        "alerts.html",
        {"settings": settings, "channels": len(alerts.channels)},
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
        "digitalocean_enabled": True,
        "checked_at": datetime.now(timezone.utc),
    }


def _status_data_disabled(settings: Settings, wg: WireGuard) -> dict:
    return {
        "droplet_id": settings.droplet.id,
        "droplet_status": "unknown",
        "public_ip": None,
        "reserved_ip": None,
        "wireguard_active": wg.is_active(),
        "digitalocean_enabled": False,
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
            issues.append("IP العام ≠ Reserved")

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


def _deep_health_disabled(wg: WireGuard) -> dict:
    checks = {
        "digitalocean_enabled": False,
        "wireguard_active": wg.is_active(),
    }
    issues = ["DigitalOcean غير مفعّل (DO_TOKEN غير مضبوط)"]
    if not checks["wireguard_active"]:
        issues.append("WireGuard متوقف")
    return {"ok": False, "checks": checks, "issues": issues}


# ---------- HTMX partials ----------
@router.get("/partials/status", response_class=HTMLResponse)
def partial_status(
    request: Request,
    settings: Settings = Depends(get_settings),
    do: DOClient | None = Depends(get_do_optional),
    wg: WireGuard = Depends(get_wg),
):
    data = (
        _status_data(settings, do, wg)
        if do is not None
        else _status_data_disabled(settings, wg)
    )
    return templates.TemplateResponse(
        request, "partials/status_card.html", {"s": data}
    )


@router.get("/partials/health", response_class=HTMLResponse)
def partial_health(
    request: Request,
    settings: Settings = Depends(get_settings),
    do: DOClient | None = Depends(get_do_optional),
    wg: WireGuard = Depends(get_wg),
):
    data = (
        _deep_health(settings, do, wg)
        if do is not None
        else _deep_health_disabled(wg)
    )
    return templates.TemplateResponse(
        request, "partials/health_card.html", {"h": data}
    )


@router.get("/partials/ip", response_class=HTMLResponse)
def partial_ip(
    request: Request,
    settings: Settings = Depends(get_settings),
    store: EventStore = Depends(get_store),
):
    result = IPMonitor(settings.monitor, store).check()
    return templates.TemplateResponse(
        request, "partials/ip_card.html", {"result": result}
    )


@router.post("/ui/ip/check", response_class=HTMLResponse)
def ui_check_ip(
    request: Request,
    settings: Settings = Depends(get_settings),
    store: EventStore = Depends(get_store),
):
    result = IPMonitor(settings.monitor, store).check()
    return templates.TemplateResponse(
        request, "partials/ip_card.html", {"result": result}
    )


@router.post("/ui/wireguard/restart", response_class=HTMLResponse)
def ui_restart_wg(
    request: Request,
    settings: Settings = Depends(get_settings),
    do: DOClient | None = Depends(get_do_optional),
    wg: WireGuard = Depends(get_wg),
):
    try:
        wg.restart()
    except Exception:
        pass
    data = (
        _status_data(settings, do, wg)
        if do is not None
        else _status_data_disabled(settings, wg)
    )
    return templates.TemplateResponse(
        request, "partials/status_card.html", {"s": data}
    )


@router.post("/ui/snapshots", response_class=HTMLResponse)
def ui_create_snapshot(
    settings: Settings = Depends(get_settings),
    do: DOClient | None = Depends(get_do_optional),
    store: EventStore = Depends(get_store),
):
    if do is None:
        return HTMLResponse(
            '<p class="bad">❌ ميزة DigitalOcean غير مفعّلة '
            '(DO_TOKEN غير مضبوط)</p>'
        )
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
    do: DOClient | None = Depends(get_do_optional),
):
    if do is None:
        return templates.TemplateResponse(
            request,
            "partials/snapshots_table.html",
            {"snaps": [], "do_disabled": True},
        )
    prefix = f"{settings.snapshot.name_prefix}-{settings.droplet.id}"
    return templates.TemplateResponse(
        request,
        "partials/snapshots_table.html",
        {"snaps": do.list_snapshots(prefix=prefix), "do_disabled": False},
    )


@router.delete("/ui/snapshots/{image_id}", response_class=HTMLResponse)
def ui_delete_snapshot(
    image_id: int,
    request: Request,
    settings: Settings = Depends(get_settings),
    do: DOClient | None = Depends(get_do_optional),
):
    if do is None:
        return templates.TemplateResponse(
            request,
            "partials/snapshots_table.html",
            {"snaps": [], "do_disabled": True},
        )
    try:
        do.delete_snapshot(image_id)
    except Exception:
        pass
    prefix = f"{settings.snapshot.name_prefix}-{settings.droplet.id}"
    return templates.TemplateResponse(
        request,
        "partials/snapshots_table.html",
        {"snaps": do.list_snapshots(prefix=prefix), "do_disabled": False},
    )


@router.get("/partials/events", response_class=HTMLResponse)
def partial_events(
    request: Request,
    limit: int = 100,
    store: EventStore = Depends(get_store),
):
    return templates.TemplateResponse(
        request, "partials/events_table.html",
        {"events": store.list_recent(limit)},
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
