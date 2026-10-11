from fastapi import APIRouter

from app.api.v1.endpoints import documents, extractions, samples, validations

api_router = APIRouter()
api_router.include_router(extractions.router)
api_router.include_router(documents.router)
api_router.include_router(validations.router)
api_router.include_router(samples.router)
