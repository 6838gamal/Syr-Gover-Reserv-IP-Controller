from fastapi import APIRouter, Depends, HTTPException

from ..config import Settings, get_settings
from ..deps import get_do, get_store, get_wg
from ..do_client import DOClient
from ..storage import EventStore
from ..wireguard import WireGuard
from ..models import ReservedIPAssignRequest, ReservedIPActionResponse

router = APIRouter(prefix="/reserved", tags=["reserved"])


@router.post("/assign", response_model=ReservedIPActionResponse)
def assign_reserved(
    body: ReservedIPAssignRequest,
    settings: Settings = Depends(get_settings),
    do: DOClient = Depends(get_do),
    wg: WireGuard = Depends(get_wg),
    store: EventStore = Depends(get_store),
):
    try:
        result = do.assign_reserved_ip(body.ip, settings.droplet.id)
        cidr = f"{body.ip}/{settings.droplet.reserved_ip_cidr}"
        updated = wg.ensure_interface_ip(cidr, settings.droplet.interface)
        store.add("reserved.assign",
                  f"{body.ip} -> droplet {settings.droplet.id}")
        return ReservedIPActionResponse(
            ip=body.ip,
            action_status=result.get("action", {}).get("status", "unknown"),
            interface_updated=updated,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unassign/{ip}")
def unassign_reserved(
    ip: str,
    do: DOClient = Depends(get_do),
    store: EventStore = Depends(get_store),
):
    try:
        result = do.unassign_reserved_ip(ip)
        store.add("reserved.unassign", ip)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
