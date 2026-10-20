import logging
import time
from typing import Any

import requests

log = logging.getLogger(__name__)
API = "https://api.digitalocean.com/v2"


class DOClient:
    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })

    def get_droplet(self, droplet_id: int) -> dict[str, Any]:
        r = self.session.get(f"{API}/droplets/{droplet_id}", timeout=15)
        r.raise_for_status()
        return r.json()["droplet"]

    def get_public_ip(self, droplet_id: int) -> str | None:
        for net in self.get_droplet(droplet_id)["networks"]["v4"]:
            if net["type"] == "public":
                return net["ip_address"]
        return None

    def list_reserved_ips(self) -> list[dict[str, Any]]:
        r = self.session.get(f"{API}/reserved_ips", timeout=15)
        r.raise_for_status()
        return r.json()["reserved_ips"]

    def assign_reserved_ip(self, ip: str, droplet_id: int) -> dict[str, Any]:
        r = self.session.post(
            f"{API}/reserved_ips/{ip}/actions",
            json={"type": "assign", "droplet_id": droplet_id},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def unassign_reserved_ip(self, ip: str) -> dict[str, Any]:
        r = self.session.post(
            f"{API}/reserved_ips/{ip}/actions",
            json={"type": "unassign"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def create_snapshot(self, droplet_id: int, name: str) -> int:
        r = self.session.post(
            f"{API}/droplets/{droplet_id}/actions",
            json={"type": "snapshot", "name": name},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()["action"]["id"]

    def get_action(self, action_id: int) -> dict[str, Any]:
        r = self.session.get(f"{API}/actions/{action_id}", timeout=15)
        r.raise_for_status()
        return r.json()["action"]

    def wait_action(self, action_id: int, timeout_s: int) -> str:
        start = time.time()
        while time.time() - start < timeout_s:
            a = self.get_action(action_id)
            if a["status"] == "completed":
                return a["status"]
            if a["status"] == "errored":
                raise RuntimeError(f"فشلت العملية: {a}")
            time.sleep(10)
        raise TimeoutError(f"العملية {action_id} تجاوزت المهلة")

    def list_snapshots(self, prefix: str = "") -> list[dict[str, Any]]:
        snaps: list[dict[str, Any]] = []
        url: str | None = f"{API}/images?type=snapshot&per_page=200"
        while url:
            r = self.session.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()
            snaps.extend(data.get("images", []))
            url = data.get("links", {}).get("pages", {}).get("next")
        if prefix:
            snaps = [s for s in snaps if s["name"].startswith(prefix)]
        snaps.sort(key=lambda s: s["created_at"])
        return snaps

    def delete_snapshot(self, image_id: int) -> None:
        r = self.session.delete(f"{API}/images/{image_id}", timeout=15)
        r.raise_for_status()
