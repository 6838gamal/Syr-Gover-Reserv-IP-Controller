from fastapi import Depends, HTTPException

from .alerts import AlertManager
from .config import Settings, get_settings
from .do_client import DOClient
from .storage import EventStore
from .watchdog import Watchdog
from .wireguard import WireGuard


def get_do_optional(settings: Settings = Depends(get_settings)) -> DOClient | None:
    """يعيد عميل DigitalOcean إن كان التوكن مضبوطاً، وإلا None."""
    if not settings.do_token:
        return None
    return DOClient(settings.do_token)


def get_do(settings: Settings = Depends(get_settings)) -> DOClient:
    """يعيد عميل DigitalOcean، أو 503 إن لم يكن مفعّلاً."""
    if not settings.do_token:
        raise HTTPException(
            status_code=503,
            detail="ميزة DigitalOcean غير مفعّلة: DO_TOKEN غير مضبوط.",
        )
    return DOClient(settings.do_token)


def get_wg(settings: Settings = Depends(get_settings)) -> WireGuard:
    return WireGuard(
        settings.wireguard.config_path,
        settings.wireguard.interface,
    )


def get_store(settings: Settings = Depends(get_settings)) -> EventStore:
    return EventStore(settings.storage.db_path)


def get_alerts(settings: Settings = Depends(get_settings)) -> AlertManager:
    return AlertManager(settings.alerts)


def get_watchdog(settings: Settings = Depends(get_settings)) -> Watchdog:
    alerts = AlertManager(settings.alerts)
    return Watchdog(
        settings.watchdog.heartbeat_file,
        settings.watchdog.stale_after_seconds,
        alerts,
    )
