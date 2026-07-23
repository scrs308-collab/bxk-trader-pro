from fastapi import APIRouter

from bxk_app.services.recommendation_service import (
    get_recommendation,
)


router = APIRouter(
    tags=["Recommendation"],
)


@router.get("/recommend")
def recommend_short():
    return get_recommendation()


@router.get("/api/recommend")
def recommend():
    return get_recommendation()