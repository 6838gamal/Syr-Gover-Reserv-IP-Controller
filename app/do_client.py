import logging
import time
from typing import Any

import requests
from fastapi import HTTPException

log = logging.getLogger(__name__)
API = "https://api.digitalocean.com/v2"
TIMEOUT = (5, 30)  # (connect, read)


class DOClient:
    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })

    # --- معالجة موحّدة للأخطاء ---
    def _handle(self, r: requests.Response) -> None:
        if r.ok:
            return
        status = r.status_code
        if status in (401, 403):
            raise HTTPException(
                status_code=502,
                detail=(
                    "فشل الاتصال بـ DigitalOcean: "
                    "التوكن غير صالح أو الصلاحيات ناقصة."
                ),
            )
        if status == 404:
            raise HTTPException(
                status_code=404,
                detail="المورد غير موجود في DigitalOcean.",
            )
        if status == 429:
            raise HTTPException(
                status_code=429,
                detail="تجاوزت حد الطلبات المسموح من DigitalOcean.",
            )
        raise HTTPException(
            status_code=502,
            detail=f"خطأ من DigitalOcean ({status}): {r.text[:200]}",
        )

    # --- عمليات ---
    def get_droplet(self, droplet_id: int) -> dict[str, Any]:
        r = self.session.get(f"{API}/droplets/{droplet_id}", timeout=TIMEOUT)
        self._handle(r)
        return r.json()["droplet"]

    def get_public_ip(self, droplet_id: int) -> str | None:
        for net in self.get_droplet(droplet_id)["networks"]["v4"]:
            if net["type"] == "public":
                return net["ip_address"]
        return None

    def list_reserved_ips(self) -> list[dict[str, Any]]:
        r = self.session.get(f"{API}/reserved_ips", timeout=TIMEOUT)
        self._handle(r)
        return r.json()["reserved_ips"]

    def assign_reserved_ip(self, ip: str, droplet_id: int) -> dict[str, Any]:
        r = self.session.post(
            f"{API}/reserved_ips/{ip}/actions",
            json={"type": "assign", "droplet_id": droplet_id},
            timeout=TIMEOUT,
        )
        self._handle(r)
        return r.json()

    def unassign_reserved_ip(self, ip: str) -> dict[str, Any]:
        r = self.session.post(
            f"{API}/reserved_ips/{ip}/actions",
            json={"type": "unassign"},
            timeout=TIMEOUT,
        )
        self._handle(r)
        return r.json()

    def create_snapshot(self, droplet_id: int, name: str) -> int:
        r = self.session.post(
            f"{API}/droplets/{droplet_id}/actions",
            json={"type": "snapshot", "name": name},
            timeout=TIMEOUT,
        )
        self._handle(r)
        return r.json()["action"]["id"]

    def get_action(self, action_id: int) -> dict[str, Any]:
        r = self.session.get(f"{API}/actions/{action_id}", timeout=TIMEOUT)
        self._handle(r)
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
            r = self.session.get(url, timeout=TIMEOUT)
            self._handle(r)
            data = r.json()
            snaps.extend(data.get("images", []))
            url = data.get("links", {}).get("pages", {}).get("next")
        if prefix:
            snaps = [s for s in snaps if s["name"].startswith(prefix)]
        snaps.sort(key=lambda s: s["created_at"])
        return snaps

    def delete_snapshot(self, image_id: int) -> None:
        r = self.session.delete(f"{API}/images/{image_id}", timeout=TIMEOUT)
        self._handle(r)

    def ping(self) -> bool:
        try:
            r = self.session.get(f"{API}/account", timeout=TIMEOUT)
            return r.ok
        except requests.RequestException:
            return False

    def close(self) -> None:
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
