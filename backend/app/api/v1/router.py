"""
API v1 Router - combines all endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, documents, questions, subjects, rubrics

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(questions.router, prefix="/questions", tags=["Questions"])
api_router.include_router(subjects.router, prefix="/subjects", tags=["Subjects"])
api_router.include_router(rubrics.router, prefix="/rubrics", tags=["Rubrics"])
