import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Structured data extraction from PDF invoices, with deterministic validation",
    version=settings.VERSION,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME, "version": settings.VERSION}
