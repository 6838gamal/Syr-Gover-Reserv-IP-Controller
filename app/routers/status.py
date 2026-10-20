from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ..alerts import Alert
from ..config import Settings, get_settings
from ..deps import get_alerts, get_do, get_wg
from ..do_client import DOClient
from ..wireguard import WireGuard
from ..alerts import AlertManager
from ..models import StatusResponse, DeepHealth

router = APIRouter(prefix="/status", tags=["status"])


@router.get("", response_model=StatusResponse)
def get_status(
    settings: Settings = Depends(get_settings),
    do: DOClient = Depends(get_do),
    wg: WireGuard = Depends(get_wg),
):
    droplet = do.get_droplet(settings.droplet.id)
    public_ip = do.get_public_ip(settings.droplet.id)
    reserved = [r for r in do.list_reserved_ips()
                if r.get("droplet", {}).get("id") == settings.droplet.id]
    return StatusResponse(
        droplet_id=settings.droplet.id,
        droplet_status=droplet["status"],
        public_ip=public_ip,
        reserved_ip=reserved[0]["ip"] if reserved else None,
        wireguard_active=wg.is_active(),
        checked_at=datetime.now(timezone.utc),
    )


@router.get("/health/deep", response_model=DeepHealth)
def deep_health(
    settings: Settings = Depends(get_settings),
    do: DOClient = Depends(get_do),
    wg: WireGuard = Depends(get_wg),
    alerts: AlertManager = Depends(get_alerts),
):
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
            issues.append(
                f"IP العام ({public_ip}) ≠ Reserved ({reserved[0]['ip']})"
            )

    try:
        snaps = do.list_snapshots(
            prefix=f"{settings.snapshot.name_prefix}-{settings.droplet.id}"
        )
        checks["has_snapshot"] = bool(snaps)
        if not snaps:
            issues.append("لا يوجد snapshots")
    except Exception:
        checks["has_snapshot"] = False

    ok = not issues
    if not ok:
        alerts.send(Alert(
            key="health.deep.failed",
            title="🚨 مشاكل في النظام",
            body="\n".join(f"• {i}" for i in issues),
        ))

    return DeepHealth(ok=ok, checks=checks, issues=issues)
