import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


class WireGuard:
    def __init__(self, config_path: str, interface: str = "wg0"):
        self.config_path = Path(config_path)
        self.interface = interface

    def is_active(self) -> bool:
        r = subprocess.run(
            ["systemctl", "is-active", "--quiet",
             f"wg-quick@{self.interface}"],
            check=False,
        )
        return r.returncode == 0

    def status(self) -> str:
        r = subprocess.run(
            ["wg", "show", self.interface],
            capture_output=True, text=True, check=False,
        )
        return (r.stdout or r.stderr).strip()

    def restart(self) -> None:
        subprocess.run(
            ["systemctl", "restart", f"wg-quick@{self.interface}"],
            check=True,
        )

    def ensure_interface_ip(self, ip_with_cidr: str, device: str) -> bool:
        out = subprocess.run(
            ["ip", "-o", "addr", "show", device],
            capture_output=True, text=True, check=True,
        ).stdout
        plain_ip = ip_with_cidr.split("/")[0]
        if plain_ip in out:
            return False
        subprocess.run(
            ["ip", "addr", "add", ip_with_cidr, "dev", device],
            check=True,
        )
        return True
