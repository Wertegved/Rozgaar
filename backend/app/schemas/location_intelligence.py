from pydantic import BaseModel, Field


class WorkerLocationRequest(BaseModel):
    location: str = Field(min_length=1, max_length=255)
    working_radius_km: int = Field(default=25, ge=0, le=200)


class ResolvedLocation(BaseModel):
    location: str
    latitude: float | None
    longitude: float | None
    resolved: bool


class RegionIntelligence(BaseModel):
    region: str
    latitude: float
    longitude: float
    worker_count: int
    available_worker_count: int
    relevant_job_count: int
    active_demand: int
    ongoing_job_count: int
    completed_job_count: int
    supply_demand_ratio: float | None
    state: str
    opportunity_score: float | None


class ConsumerLocationIntelligence(BaseModel):
    location: ResolvedLocation
    category: str
    nearby_worker_count: int
    available_worker_count: int
    supply_level: str
    demand_level: str
    regions: list[RegionIntelligence]


class WorkerLocationIntelligence(BaseModel):
    location: ResolvedLocation
    working_radius_km: int | None
    regions: list[RegionIntelligence]
    recommendations: list[RegionIntelligence]