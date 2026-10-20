import logging
from datetime import datetime, timezone
from pathlib import Path

from .alerts import Alert, AlertManager

log = logging.getLogger(__name__)


class Watchdog:
    def __init__(self, heartbeat_file: str, stale_after: int,
                 alerts: AlertManager):
        self.path = Path(heartbeat_file)
        self.stale_after = stale_after
        self.alerts = alerts
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._was_stale = False

    def beat(self) -> None:
        self.path.write_text(
            datetime.now(timezone.utc).isoformat(),
            encoding="utf-8",
        )
        self._was_stale = False

    def check_stale(self) -> bool:
        if not self.path.exists():
            return False
        try:
            last = datetime.fromisoformat(
                self.path.read_text(encoding="utf-8").strip()
            )
        except ValueError:
            return False

        age = (datetime.now(timezone.utc) - last).total_seconds()
        if age > self.stale_after:
            if not self._was_stale:
                self.alerts.send(Alert(
                    key="watchdog.stale",
                    title="⚠️ السيرفر لا يستجيب",
                    body=(
                        f"مرت {age/60:.0f} دقيقة بدون heartbeat.\n"
                        f"قد يحتاج السيرفر إعادة تشغيل أو rebuild يدوي.\n"
                        f"https://cloud.digitalocean.com/droplets"
                    ),
                ))
                self._was_stale = True
            return True
        return False
