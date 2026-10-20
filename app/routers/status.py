from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ..alerts import Alert, AlertManager
from ..config import Settings, get_settings
from ..deps import get_alerts, get_do_optional, get_wg
from ..do_client import DOClient
from ..models import StatusResponse, DeepHealth
from ..wireguard import WireGuard

router = APIRouter(prefix="/status", tags=["status"])


@router.get("", response_model=StatusResponse)
def get_status(
    settings: Settings = Depends(get_settings),
    do: DOClient | None = Depends(get_do_optional),
    wg: WireGuard = Depends(get_wg),
):
    now = datetime.now(timezone.utc)

    if do is None:
        # DigitalOcean غير مفعّل — نعيد حالة جزئية
        return StatusResponse(
            droplet_id=settings.droplet.id,
            droplet_status="unknown",
            public_ip=None,
            reserved_ip=None,
            wireguard_active=wg.is_active(),
            digitalocean_enabled=False,
            checked_at=now,
        )

    try:
        droplet = do.get_droplet(settings.droplet.id)
        public_ip = do.get_public_ip(settings.droplet.id)
        reserved = [
            r for r in do.list_reserved_ips()
            if r.get("droplet", {}).get("id") == settings.droplet.id
        ]
    except Exception:
        return StatusResponse(
            droplet_id=settings.droplet.id,
            droplet_status="error",
            public_ip=None,
            reserved_ip=None,
            wireguard_active=wg.is_active(),
            digitalocean_enabled=True,
            checked_at=now,
        )

    return StatusResponse(
        droplet_id=settings.droplet.id,
        droplet_status=droplet["status"],
        public_ip=public_ip,
        reserved_ip=reserved[0]["ip"] if reserved else None,
        wireguard_active=wg.is_active(),
        digitalocean_enabled=True,
        checked_at=now,
    )


@router.get("/health/deep", response_model=DeepHealth)
def deep_health(
    settings: Settings = Depends(get_settings),
    do: DOClient | None = Depends(get_do_optional),
    wg: WireGuard = Depends(get_wg),
    alerts: AlertManager = Depends(get_alerts),
):
    checks: dict[str, bool] = {}
    issues: list[str] = []

    checks["digitalocean_enabled"] = do is not None
    if do is None:
        issues.append("DigitalOcean غير مفعّل (DO_TOKEN غير مضبوط)")

    checks["wireguard_active"] = wg.is_active()
    if not checks["wireguard_active"]:
        issues.append("WireGuard متوقف")

    reserved: list[dict] = []
    if do is not None:
        try:
            reserved = [
                r for r in do.list_reserved_ips()
                if r.get("droplet", {}).get("id") == settings.droplet.id
            ]
            checks["reserved_ip_bound"] = bool(reserved)
            if not reserved:
                issues.append("لا يوجد Reserved IP مربوط")
        except Exception as e:
            checks["reserved_ip_bound"] = False
            issues.append(f"فشل الاستعلام من DigitalOcean: {e}")

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
        except Exception as e:
            checks["has_snapshot"] = False
            issues.append(f"فشل جلب الـ snapshots: {e}")

    ok = not issues
    if not ok:
        alerts.send(Alert(
            key="health.deep.failed",
            title="🚨 مشاكل في النظام",
            body="\n".join(f"• {i}" for i in issues),
        ))

    return DeepHealth(ok=ok, checks=checks, issues=issues)
