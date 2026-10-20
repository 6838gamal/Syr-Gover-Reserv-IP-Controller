from fastapi import APIRouter, Depends

from ..config import Settings, get_settings
from ..deps import get_store
from ..storage import EventStore
from ..monitor import IPMonitor
from ..models import IPCheckResponse, EventOut

router = APIRouter(prefix="/ip", tags=["ip"])


@router.post("/check", response_model=IPCheckResponse)
def check_ip(
    settings: Settings = Depends(get_settings),
    store: EventStore = Depends(get_store),
):
    return IPMonitor(settings.monitor, store).check()


@router.get("/events", response_model=list[EventOut])
def list_events(limit: int = 50, store: EventStore = Depends(get_store)):
    return store.list_recent(limit)
