from datetime import datetime
from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    droplet_id: int
    droplet_status: str
    public_ip: str | None
    reserved_ip: str | None
    wireguard_active: bool
    checked_at: datetime


class DeepHealth(BaseModel):
    ok: bool
    checks: dict[str, bool]
    issues: list[str]


class IPCheckResponse(BaseModel):
    ok: bool
    ip: str | None = None
    changed: bool = False
    previous_ip: str | None = None
    error: str | None = None
    checked_at: datetime


class SnapshotRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)


class SnapshotResponse(BaseModel):
    name: str
    action_id: int
    status: str
    deleted_old: int


class SnapshotInfo(BaseModel):
    id: int
    name: str
    created_at: str


class ReservedIPAssignRequest(BaseModel):
    ip: str


class ReservedIPActionResponse(BaseModel):
    ip: str
    action_status: str
    interface_updated: bool


class WireGuardStatus(BaseModel):
    interface: str
    active: bool
    output: str


class EventOut(BaseModel):
    id: int
    ts: datetime
    kind: str
    message: str


class AlertsUpdateRequest(BaseModel):
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    email_enabled: bool = False
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_smtp_user: str = ""
    email_smtp_password: str = ""
    email_from: str = ""
    email_to: str = ""
    webhook_enabled: bool = False
    webhook_url: str = ""
    cooldown_seconds: int = 1800
