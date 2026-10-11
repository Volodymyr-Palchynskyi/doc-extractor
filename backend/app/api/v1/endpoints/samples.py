from fastapi import APIRouter, HTTPException, Response, status

from app.core.config import settings
from app.schemas.info import AppInfo, SampleInfo
from app.services.demo_extractor import get_samples

router = APIRouter(tags=["Samples"])


@router.get("/info", response_model=AppInfo, summary="Mode and limits, for the UI")
async def info() -> AppInfo:
    return AppInfo(
        mode=settings.extractor_mode,
        max_upload_mb=settings.MAX_UPLOAD_MB,
        max_pages=settings.MAX_PDF_PAGES,
        document_ttl_s=settings.DOC_TTL_S,
    )


@router.get("/samples", response_model=list[SampleInfo], summary="Bundled sample invoices to try")
async def list_samples() -> list[SampleInfo]:
    return [SampleInfo(id=s.id, title=s.title, description=s.description, file_name=s.file_name) for s in get_samples()]


@router.get("/samples/{sample_id}/pdf", summary="Download a sample invoice", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}})
async def sample_pdf(sample_id: str) -> Response:
    sample = next((s for s in get_samples() if s.id == sample_id), None)
    if sample is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such sample.")
    return Response(content=sample.pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{sample.file_name}"'})
