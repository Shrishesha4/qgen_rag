"""
API v1 Router - combines all endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, documents, questions, subjects, rubrics, vetter, training, models, admin, websocket, settings

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(questions.router, prefix="/questions", tags=["Questions"])
api_router.include_router(subjects.router, prefix="/subjects", tags=["Subjects"])
api_router.include_router(rubrics.router, prefix="/rubrics", tags=["Rubrics"])
api_router.include_router(vetter.router, prefix="/vetter", tags=["Vetter Portal"])
api_router.include_router(training.router, prefix="/training", tags=["Training Pipeline"])
api_router.include_router(models.router, prefix="/models", tags=["Model Operations"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin Dashboard"])
api_router.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
