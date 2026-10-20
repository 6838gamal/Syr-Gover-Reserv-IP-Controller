import logging
from datetime import datetime, timezone

from .config import DropletCfg, SnapshotCfg
from .do_client import DOClient
from .storage import EventStore

log = logging.getLogger(__name__)


class SnapshotManager:
    def __init__(self, do: DOClient, dropl: DropletCfg,
                 cfg: SnapshotCfg, store: EventStore):
        self.do = do
        self.droplet = dropl
        self.cfg = cfg
        self.store = store

    def run(self, custom_name: str | None = None) -> dict:
        name = custom_name or (
            f"{self.cfg.name_prefix}-{self.droplet.id}-"
            f"{datetime.now(timezone.utc):%Y-%m-%d-%H%M}"
        )
        action_id = self.do.create_snapshot(self.droplet.id, name)
        status = self.do.wait_action(action_id, self.cfg.wait_timeout_seconds)
        deleted = self._prune()
        self.store.add("snapshot.created", f"{name} (deleted_old={deleted})")
        return {"name": name, "action_id": action_id,
                "status": status, "deleted_old": deleted}

    def _prune(self) -> int:
        prefix = f"{self.cfg.name_prefix}-{self.droplet.id}"
        snaps = self.do.list_snapshots(prefix=prefix)
        excess = len(snaps) - self.cfg.keep
        if excess <= 0:
            return 0
        for s in snaps[:excess]:
            self.do.delete_snapshot(s["id"])
        return excess
