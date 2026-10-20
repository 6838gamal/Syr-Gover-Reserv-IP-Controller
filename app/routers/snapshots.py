from fastapi import APIRouter, Depends, HTTPException

from ..config import Settings, get_settings
from ..deps import get_do, get_store
from ..do_client import DOClient
from ..storage import EventStore
from ..snapshot import SnapshotManager
from ..models import SnapshotRequest, SnapshotResponse, SnapshotInfo

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.post("", response_model=SnapshotResponse)
def create_snapshot(
    body: SnapshotRequest,
    settings: Settings = Depends(get_settings),
    do: DOClient = Depends(get_do),
    store: EventStore = Depends(get_store),
):
    try:
        mgr = SnapshotManager(do, settings.droplet, settings.snapshot, store)
        return mgr.run(body.name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[SnapshotInfo])
def list_snapshots(
    settings: Settings = Depends(get_settings),
    do: DOClient = Depends(get_do),
):
    prefix = f"{settings.snapshot.name_prefix}-{settings.droplet.id}"
    return [
        {"id": s["id"], "name": s["name"], "created_at": s["created_at"]}
        for s in do.list_snapshots(prefix=prefix)
    ]


@router.delete("/{image_id}")
def delete_snapshot(image_id: int, do: DOClient = Depends(get_do)):
    try:
        do.delete_snapshot(image_id)
        return {"ok": True, "deleted": image_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
