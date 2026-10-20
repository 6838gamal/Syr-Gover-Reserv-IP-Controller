import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DropletCfg:
    id: int
    region: str
    interface: str
    reserved_ip_cidr: int = 20


@dataclass
class WireGuardCfg:
    interface: str
    listen_port: int
    config_path: str


@dataclass
class MonitorCfg:
    state_file: str
    check_url: str


@dataclass
class SnapshotCfg:
    keep: int
    name_prefix: str
    wait_timeout_seconds: int


@dataclass
class StorageCfg:
    db_path: str


@dataclass
class TelegramCfg:
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""


@dataclass
class EmailCfg:
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_: str = ""
    to: str = ""


@dataclass
class WebhookCfg:
    enabled: bool = False
    url: str = ""


@dataclass
class AlertsCfg:
    telegram: TelegramCfg = field(default_factory=TelegramCfg)
    email: EmailCfg = field(default_factory=EmailCfg)
    webhook: WebhookCfg = field(default_factory=WebhookCfg)
    cooldown_seconds: int = 1800


@dataclass
class WatchdogCfg:
    heartbeat_file: str = "/var/lib/do-wg/heartbeat.txt"
    stale_after_seconds: int = 600
    check_interval_seconds: int = 60


@dataclass
class Settings:
    droplet: DropletCfg
    wireguard: WireGuardCfg
    monitor: MonitorCfg
    snapshot: SnapshotCfg
    storage: StorageCfg
    alerts: AlertsCfg
    watchdog: WatchdogCfg
    do_token: str
    log_level: str


def _mk_droplet(d: dict[str, Any]) -> DropletCfg:
    return DropletCfg(**d)


def _mk_wireguard(d: dict[str, Any]) -> WireGuardCfg:
    return WireGuardCfg(**d)


def _mk_monitor(d: dict[str, Any]) -> MonitorCfg:
    return MonitorCfg(**d)


def _mk_snapshot(d: dict[str, Any]) -> SnapshotCfg:
    return SnapshotCfg(**d)


def _mk_storage(d: dict[str, Any]) -> StorageCfg:
    return StorageCfg(**d)


def _mk_alerts(d: dict[str, Any] | None) -> AlertsCfg:
    if not d:
        return AlertsCfg()
    em = d.get("email") or {}
    if "from" in em and "from_" not in em:
        em["from_"] = em.pop("from")
    return AlertsCfg(
        telegram=TelegramCfg(**(d.get("telegram") or {})),
        email=EmailCfg(**em),
        webhook=WebhookCfg(**(d.get("webhook") or {})),
        cooldown_seconds=d.get("cooldown_seconds", 1800),
    )


def _mk_watchdog(d: dict[str, Any] | None) -> WatchdogCfg:
    return WatchdogCfg(**(d or {}))


@lru_cache
def get_settings(path: str = "config.yaml") -> Settings:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    do_token = os.getenv("DO_TOKEN")
    if not do_token:
        raise RuntimeError("DO_TOKEN مفقود في .env")

    return Settings(
        droplet=_mk_droplet(raw["droplet"]),
        wireguard=_mk_wireguard(raw["wireguard"]),
        monitor=_mk_monitor(raw["monitor"]),
        snapshot=_mk_snapshot(raw["snapshot"]),
        storage=_mk_storage(raw["storage"]),
        alerts=_mk_alerts(raw.get("alerts")),
        watchdog=_mk_watchdog(raw.get("watchdog")),
        do_token=do_token,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
