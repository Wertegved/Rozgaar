from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin, require_consumer, require_worker
from app.db.models.users import User
from app.db.session import get_db
from app.schemas.location_intelligence import ConsumerLocationIntelligence, WorkerLocationIntelligence, WorkerLocationRequest
from app.services.location_intelligence_service import consumer_intelligence, region_intelligence, resolve_location, worker_intelligence, worker_profile


router = APIRouter(prefix="/location-intelligence", tags=["location intelligence"])


@router.get("/consumer", response_model=ConsumerLocationIntelligence)
def consumer(location: str = Query(min_length=1), category: str = Query(min_length=1), user: User = Depends(require_consumer), session: Session = Depends(get_db)) -> ConsumerLocationIntelligence:
    return consumer_intelligence(session, location, category)


@router.get("/worker", response_model=WorkerLocationIntelligence)
def worker(user: User = Depends(require_worker), session: Session = Depends(get_db)) -> WorkerLocationIntelligence:
    return worker_intelligence(session, worker_profile(session, user))


@router.patch("/worker/location", response_model=WorkerLocationIntelligence)
def update_worker_location(data: WorkerLocationRequest, user: User = Depends(require_worker), session: Session = Depends(get_db)) -> WorkerLocationIntelligence:
    profile = worker_profile(session, user)
    coordinates = resolve_location(data.location)
    profile.working_location = data.location
    profile.working_radius_km = data.working_radius_km
    profile.working_latitude, profile.working_longitude = coordinates or (None, None)
    session.commit()
    return worker_intelligence(session, profile)


@router.get("/admin", response_model=list[WorkerLocationIntelligence])
def admin(city: str | None = None, category: str | None = None, user: User = Depends(require_admin), session: Session = Depends(get_db)) -> list[WorkerLocationIntelligence]:
    regions = region_intelligence(session, category)
    if city:
        regions = [region for region in regions if city.lower() in region.region.lower()]
    return [WorkerLocationIntelligence(location={"location": city or "All available regions", "latitude": None, "longitude": None, "resolved": bool(regions)}, working_radius_km=None, regions=regions, recommendations=[])]