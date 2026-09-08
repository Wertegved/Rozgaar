from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.jobs import router as jobs_router
from app.api.applications import router as applications_router
from app.api.negotiations import router as negotiations_router
from app.api.scheduling import router as scheduling_router
from app.api.payments import router as payments_router
from app.api.completion import router as completion_router
from app.api.reviews import router as reviews_router
from app.api.issues import router as issues_router
from app.api.notifications import router as notifications_router
from app.api.location_intelligence import router as location_intelligence_router
from app.health.router import router as health_router


router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(jobs_router)
router.include_router(applications_router)
router.include_router(negotiations_router)
router.include_router(scheduling_router)
router.include_router(payments_router)
router.include_router(completion_router)
router.include_router(reviews_router)
router.include_router(issues_router)
router.include_router(notifications_router)
router.include_router(location_intelligence_router)