"""Model operations endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.training_service import TrainingService


router = APIRouter()
training_service = TrainingService()


@router.get("/live-metrics", response_model=dict)
async def get_live_model_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return live model health and quality metrics for operations dashboards."""
    return await training_service.get_live_metrics(db=db)
