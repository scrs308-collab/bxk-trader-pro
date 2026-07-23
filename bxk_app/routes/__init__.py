from fastapi import APIRouter

from bxk_app.routes.broker import (
    router as broker_router,
)
from bxk_app.routes.health import (
    router as health_router,
)
from bxk_app.routes.market import (
    router as market_router,
)
from bxk_app.routes.recommendation import (
    router as recommendation_router,
)
   
from bxk_app.routes.positions import (
    router as positions_router,
)
from bxk_app.routes.options import (
    router as options_router,
)
from bxk_app.routes.scanner import (
    router as scanner_router,
)
from bxk_app.routes.debug import (
    router as debug_router,
)

router = APIRouter()

router.include_router(health_router)
router.include_router(market_router)
router.include_router(recommendation_router)
router.include_router(broker_router)
router.include_router(positions_router)
router.include_router(options_router)
router.include_router(scanner_router)
router.include_router(debug_router)