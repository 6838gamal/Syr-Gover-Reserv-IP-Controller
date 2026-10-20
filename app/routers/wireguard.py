from fastapi import APIRouter, Depends

from ..deps import get_wg
from ..wireguard import WireGuard
from ..models import WireGuardStatus

router = APIRouter(prefix="/wireguard", tags=["wireguard"])


@router.get("/status", response_model=WireGuardStatus)
def wg_status(wg: WireGuard = Depends(get_wg)):
    return WireGuardStatus(
        interface=wg.interface,
        active=wg.is_active(),
        output=wg.status(),
    )


@router.post("/restart")
def wg_restart(wg: WireGuard = Depends(get_wg)):
    wg.restart()
    return {"ok": True, "active": wg.is_active()}
