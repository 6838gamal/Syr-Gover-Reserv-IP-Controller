import logging

from fastapi import APIRouter, Depends, HTTPException

from ..alerts import Alert
from ..config import Settings, get_settings
from ..deps import get_alerts
from ..alerts import AlertManager
from ..models import AlertsUpdateRequest

log = logging.getLogger(__name__)
router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("/test")
def test_alert(
    settings: Settings = Depends(get_settings),
    alerts: AlertManager = Depends(get_alerts),
):
    if not alerts.channels:
        raise HTTPException(
            status_code=400,
            detail="لا قنوات مفعّلة — فعّل Telegram/بريد/Webhook أولاً",
        )
    alerts.channels[0].send(
        "✅ اختبار تنبيه",
        "إذا وصلتك هذه الرسالة، فالتنبيهات تعمل.",
    )
    return {"ok": True, "channels": len(alerts.channels)}


@router.get("/config")
def get_alert_config(settings: Settings = Depends(get_settings)):
    a = settings.alerts
    return {
        "telegram_enabled": a.telegram.enabled,
        "telegram_bot_token_set": bool(a.telegram.bot_token),
        "telegram_chat_id": a.telegram.chat_id,
        "email_enabled": a.email.enabled,
        "email_smtp_host": a.email.smtp_host,
        "email_smtp_port": a.email.smtp_port,
        "email_smtp_user": a.email.smtp_user,
        "email_smtp_password_set": bool(a.email.smtp_password),
        "email_from": a.email.from_,
        "email_to": a.email.to,
        "webhook_enabled": a.webhook.enabled,
        "webhook_url_set": bool(a.webhook.url),
        "cooldown_seconds": a.cooldown_seconds,
    }
