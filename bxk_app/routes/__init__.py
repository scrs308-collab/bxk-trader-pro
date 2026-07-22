from fastapi import APIRouter

from bxk_app.routes.health import (
    router as health_router,
)
from bxk_app.routes.market import (
    router as market_router,
)
from bxk_app.routes.recommendation import (
    router as recommendation_router,
)
from bxk_app.routes_old import (
    router as legacy_router,
)

router = APIRouter()

router.include_router(health_router)
router.include_router(market_router)
router.include_router(recommendation_router)
router.include_router(legacy_router)