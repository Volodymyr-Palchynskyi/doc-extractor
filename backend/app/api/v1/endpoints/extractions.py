import asyncio
import logging

import pypdfium2 as pdfium
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.api.deps import acquire_extraction_slot, get_extractor
from app.core.config import settings
from app.schemas.invoice import ExtractionResult
from app.services.extraction_service import PdfExtractor, extract_and_validate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/extractions", tags=["Extractions"])

PDF_MAGIC = b"%PDF-"


def _count_pages(pdf: bytes) -> int:
    """Also proves the file is a readable PDF (corrupt or password-protected files raise)."""
    try:
        return len(pdfium.PdfDocument(pdf))
    except pdfium.PdfiumError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The file is not a readable PDF (corrupt or password-protected).") from exc


async def read_valid_pdf(file: UploadFile) -> bytes:
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read(limit + 1)  # never buffer more than the limit plus one byte
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"The file is larger than {settings.MAX_UPLOAD_MB} MB.")
    # The declared content type is client-controlled, so check the content itself.
    if not data.startswith(PDF_MAGIC):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only PDF files are supported.")
    pages = await asyncio.to_thread(_count_pages, data)
    if pages > settings.MAX_PDF_PAGES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"The PDF has {pages} pages, the limit is {settings.MAX_PDF_PAGES}.")
    return data


@router.post(
    "",
    response_model=ExtractionResult,
    summary="Extract structured data from an invoice PDF",
    description="Returns the extracted fields, the arithmetic and consistency issues found by the validator, "
                "and `needs_review` when a human should check the result.",
)
async def create_extraction(
    file: UploadFile,
    extractor: PdfExtractor = Depends(get_extractor),
    _slot: None = Depends(acquire_extraction_slot),
) -> ExtractionResult:
    pdf = await read_valid_pdf(file)
    try:
        return await extract_and_validate(extractor, pdf)
    except Exception:
        logger.exception("Extraction failed")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Extraction failed. Please try again.")
