import logging
from datetime import datetime, timezone
from pathlib import Path

import requests

from .config import MonitorCfg
from .storage import EventStore

log = logging.getLogger(__name__)


class IPMonitor:
    def __init__(self, cfg: MonitorCfg, store: EventStore):
        self.cfg = cfg
        self.store = store
        self.state = Path(cfg.state_file)
        self.state.parent.mkdir(parents=True, exist_ok=True)

    def _current_ip(self) -> str:
        r = requests.get(self.cfg.check_url, timeout=15)
        r.raise_for_status()
        return r.text.strip()

    def _last_ip(self) -> str | None:
        if self.state.exists():
            return self.state.read_text(encoding="utf-8").strip()
        return None

    def check(self) -> dict:
        now = datetime.now(timezone.utc)
        try:
            current = self._current_ip()
        except requests.RequestException as e:
            self.store.add("ip.error", str(e))
            return {"ok": False, "error": str(e), "checked_at": now}

        last = self._last_ip()
        if last is None:
            self.state.write_text(current, encoding="utf-8")
            self.store.add("ip.init", current)
            return {"ok": True, "ip": current, "changed": False,
                    "checked_at": now}

        if current != last:
            self.state.write_text(current, encoding="utf-8")
            self.store.add("ip.changed", f"{last} -> {current}")
            return {
                "ok": True, "ip": current, "changed": True,
                "previous_ip": last, "checked_at": now,
            }

        return {"ok": True, "ip": current, "changed": False,
                "checked_at": now}
