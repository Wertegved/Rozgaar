import json
import re
from collections import Counter
from math import atan2, cos, radians, sin, sqrt
from urllib.parse import quote
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.db.models.agreements import Agreement
from app.db.models.enums import AgreementStatus, JobStatus
from app.db.models.jobs import Job
from app.db.models.users import User, WorkerProfile, WorkerSkill
from app.schemas.location_intelligence import ConsumerLocationIntelligence, NearbyWorkerSummary, RegionIntelligence, ResolvedLocation, WorkerLocationIntelligence


GRID = 100
OPEN_STATUSES = {JobStatus.POSTED, JobStatus.APPLICATIONS}
ONGOING_STATUSES = {JobStatus.ACCEPTED, JobStatus.ADVANCE_PAID, JobStatus.STARTED, JobStatus.COMPLETION_PENDING, JobStatus.DISPUTED}


def resolve_location(location: str) -> tuple[float, float] | None:
    request = Request(
        f"https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q={quote(location.strip())}",
        headers={"User-Agent": "Rozgaar/1.0 location intelligence"},
    )
    try:
        with urlopen(request, timeout=4) as response:
            results = json.loads(response.read().decode("utf-8"))
        return (float(results[0]["lat"]), float(results[0]["lon"])) if results else None
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return None


def _distance_km(first_lat: float, first_lon: float, second_lat: float, second_lon: float) -> float:
    lat_delta = radians(second_lat - first_lat)
    lon_delta = radians(second_lon - first_lon)
    value = sin(lat_delta / 2) ** 2 + cos(radians(first_lat)) * cos(radians(second_lat)) * sin(lon_delta / 2) ** 2
    return 6371.0 * 2 * atan2(sqrt(value), sqrt(1 - value))


CITY_TOKENS = {
    "ahmedabad",
    "bangalore",
    "chennai",
    "delhi",
    "gurugram",
    "hyderabad",
    "jaipur",
    "kolkata",
    "mumbai",
    "noida",
    "pune",
    "thane",
}


def _canonical_region_key(value: str | None) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value or "Regional area").lower()).strip()
    return " ".join(normalized.split()) or "regional area"


def _canonical_region_label(value: str | None) -> str:
    key = _canonical_region_key(value)
    if key == "regional area":
        return "Regional area"
    tokens = key.split()
    if len(tokens) > 1 and tokens[-1] in CITY_TOKENS:
        area_tokens = tokens[:-1]
        area = " ".join(part.capitalize() for part in area_tokens)
        city = tokens[-1].capitalize()
        return f"{area}, {city}"
    return " ".join(part.capitalize() for part in tokens)


def _region_key(latitude: float, longitude: float) -> tuple[float, float]:
    return round(latitude * GRID) / GRID, round(longitude * GRID) / GRID


def _canonical_coordinates(votes: Counter[tuple[float, float]]) -> tuple[float, float]:
    if not votes:
        return 0.0, 0.0
    (latitude, longitude), _ = max(votes.items(), key=lambda item: (item[1], abs(item[0][0]) + abs(item[0][1])))
    return float(latitude), float(longitude)


def _available_worker(worker: WorkerProfile, locked_worker_ids: set) -> bool:
    return worker.id not in locked_worker_ids and worker.availability != "UNAVAILABLE"


def _location_tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {token for token in re.sub(r"[^a-z0-9]+", " ", str(value).lower()).split() if token}


def _location_matches(left: str | None, right: str | None) -> bool:
    left_tokens = _location_tokens(left)
    right_tokens = _location_tokens(right)
    if not left_tokens or not right_tokens:
        return bool(left and right and (str(left).lower() in str(right).lower() or str(right).lower() in str(left).lower()))
    return bool(left_tokens & right_tokens)


def _is_worker_nearby(worker: WorkerProfile, target_latitude: float, target_longitude: float, radius_km: float = 25.0) -> bool:
    if worker.working_latitude is None or worker.working_longitude is None:
        return False
    return _distance_km(float(worker.working_latitude), float(worker.working_longitude), target_latitude, target_longitude) <= radius_km


def _worker_summary(worker: WorkerProfile) -> NearbyWorkerSummary:
    return NearbyWorkerSummary(
        id=str(worker.id),
        name=worker.user.name if worker.user is not None else "Worker",
        location=worker.working_location,
        availability=worker.availability,
        skills=[skill.skill.name for skill in worker.skills if skill.skill],
    )


def _worker_matches_category(worker: WorkerProfile, category: str) -> bool:
    requested = _location_tokens(category)
    skills = set().union(*(_location_tokens(skill.skill.name) for skill in worker.skills if skill.skill))
    return bool(requested & skills)


def region_intelligence(session: Session, category: str | None = None) -> list[RegionIntelligence]:
    workers = list(session.scalars(select(WorkerProfile).join(User).where(User.account_status == "ACTIVE").options(selectinload(WorkerProfile.skills).selectinload(WorkerSkill.skill))))
    jobs = list(session.scalars(select(Job).where(Job.latitude.is_not(None), Job.longitude.is_not(None))))
    locked_worker_ids = set(session.scalars(select(Agreement.worker_id).where(Agreement.status.in_([AgreementStatus.PENDING, AgreementStatus.ACTIVE]))))
    regions: dict[str, dict] = {}
    for worker in workers:
        if worker.working_latitude is None or worker.working_longitude is None:
            continue
        skill_names = [item.skill.name.lower() for item in worker.skills if item.skill]
        if category and category.lower() not in skill_names and category.lower() not in (worker.working_location or "").lower():
            continue
        label = _canonical_region_label(worker.working_location)
        key = _canonical_region_key(label)
        bucket = regions.setdefault(key, {"workers": 0, "available": 0, "jobs": [], "label": label, "coord_votes": Counter()})
        bucket["label"] = label
        bucket["workers"] += 1
        bucket["available"] += int(_available_worker(worker, locked_worker_ids))
        bucket["coord_votes"][(float(worker.working_latitude), float(worker.working_longitude))] += 1
    for job in jobs:
        if category and category.lower() not in job.category.lower():
            continue
        label = _canonical_region_label(job.location)
        key = _canonical_region_key(label)
        bucket = regions.setdefault(key, {"workers": 0, "available": 0, "jobs": [], "label": label, "coord_votes": Counter()})
        bucket["label"] = label
        bucket["jobs"].append(job)
        bucket["coord_votes"][(float(job.latitude), float(job.longitude))] += 1
    result = []
    for bucket in regions.values():
        latitude, longitude = _canonical_coordinates(bucket["coord_votes"])
        relevant_jobs = bucket["jobs"]
        demand = sum(job.required_worker_count for job in relevant_jobs if job.status in OPEN_STATUSES)
        available = bucket["available"]
        ratio = round(demand / available, 2) if available else None
        state = "UNDERSERVED" if demand and not available else "SHORTAGE" if ratio and ratio > 1 else "OVERSUPPLIED" if available and ratio is not None and ratio < 0.5 else "BALANCED"
        score = round(min(100, demand / max(available, 1) * 50), 1)
        result.append(RegionIntelligence(region=bucket["label"], latitude=latitude, longitude=longitude, worker_count=bucket["workers"], available_worker_count=available, relevant_job_count=len(relevant_jobs), active_demand=demand, ongoing_job_count=sum(job.required_worker_count for job in relevant_jobs if job.status in ONGOING_STATUSES), completed_job_count=sum(job.required_worker_count for job in relevant_jobs if job.status is JobStatus.COMPLETED), supply_demand_ratio=ratio, state=state, opportunity_score=score))
    return sorted(result, key=lambda item: item.opportunity_score or 0, reverse=True)


def consumer_intelligence(session: Session, location: str, category: str) -> ConsumerLocationIntelligence:
    coordinates = resolve_location(location)
    resolved = ResolvedLocation(location=location, latitude=coordinates[0] if coordinates else None, longitude=coordinates[1] if coordinates else None, resolved=coordinates is not None)
    if coordinates is None:
        workers = list(session.scalars(select(WorkerProfile).join(User).where(User.account_status == "ACTIVE").options(selectinload(WorkerProfile.skills).selectinload(WorkerSkill.skill))))
        matching_workers = [
            _worker_summary(worker)
            for worker in workers
            if worker.availability != "UNAVAILABLE" and _worker_matches_category(worker, category) and worker.working_location and _location_matches(worker.working_location, location)
        ]
        return ConsumerLocationIntelligence(location=resolved, category=category, nearby_worker_count=len(matching_workers), available_worker_count=len(matching_workers), supply_level="HIGH" if matching_workers else "LOW", demand_level="LOW", regions=[], nearby_workers=matching_workers[:12])
    regions = [item for item in region_intelligence(session, category) if _distance_km(coordinates[0], coordinates[1], item.latitude, item.longitude) <= 25]
    available = sum(item.available_worker_count for item in regions)
    demand = sum(item.active_demand for item in regions)
    supply_level = "HIGH" if available >= demand * 2 and available else "MODERATE" if available else "LOW"
    demand_level = "HIGH" if demand > available else "MODERATE" if demand else "LOW"
    workers = list(session.scalars(select(WorkerProfile).join(User).where(User.account_status == "ACTIVE").options(selectinload(WorkerProfile.skills).selectinload(WorkerSkill.skill))))
    nearby_workers = [
        _worker_summary(worker)
        for worker in workers
        if worker.availability != "UNAVAILABLE" and _worker_matches_category(worker, category)
        and (
            (_is_worker_nearby(worker, coordinates[0], coordinates[1], 25.0))
            or (worker.working_location and _location_matches(worker.working_location, location))
        )
    ]
    nearby_count = sum(item.worker_count for item in regions) or len(nearby_workers)
    available_count = available or len(nearby_workers)
    return ConsumerLocationIntelligence(location=resolved, category=category, nearby_worker_count=nearby_count, available_worker_count=available_count, supply_level=supply_level, demand_level=demand_level, regions=regions[:12], nearby_workers=nearby_workers[:12])


def worker_profile(session: Session, user: User) -> WorkerProfile:
    worker = session.scalar(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    if worker is None:
        raise APIError(409, "Worker profile is not available")
    return worker


def worker_intelligence(session: Session, worker: WorkerProfile) -> WorkerLocationIntelligence:
    resolved = ResolvedLocation(location=worker.working_location or "", latitude=float(worker.working_latitude) if worker.working_latitude is not None else None, longitude=float(worker.working_longitude) if worker.working_longitude is not None else None, resolved=worker.working_latitude is not None and worker.working_longitude is not None)
    if not resolved.resolved:
        return WorkerLocationIntelligence(location=resolved, working_radius_km=worker.working_radius_km, regions=[], recommendations=[])
    radius = max(worker.working_radius_km or 25, 1)
    regions = [item for item in region_intelligence(session) if _distance_km(resolved.latitude, resolved.longitude, item.latitude, item.longitude) <= radius]
    current = _region_key(resolved.latitude, resolved.longitude)
    recommendations = [item for item in regions if (item.latitude, item.longitude) != current and item.state in {"SHORTAGE", "UNDERSERVED"}]
    return WorkerLocationIntelligence(location=resolved, working_radius_km=worker.working_radius_km, regions=regions[:20], recommendations=recommendations[:5])