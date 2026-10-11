from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import limit_validations
from app.schemas.invoice import InvoiceExtraction, ValidationResult
from app.services.validation import validate_invoice

router = APIRouter(prefix="/validations", tags=["Validations"])

MAX_LINE_ITEMS = 500  # bounds the work a single request can ask for


@router.post(
    "",
    response_model=ValidationResult,
    summary="Re-check values (for example after a human edited them)",
    description="Runs the same deterministic checks as an extraction, with no model call, so it is cheap "
                "enough to run after every edit. It checks arithmetic and consistency only: it cannot know "
                "whether the values match the document.",
    dependencies=[Depends(limit_validations)],
)
async def validate(invoice: InvoiceExtraction) -> ValidationResult:
    if len(invoice.line_items) > MAX_LINE_ITEMS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"At most {MAX_LINE_ITEMS} line items are accepted.")
    issues = validate_invoice(invoice)
    return ValidationResult(issues=issues, needs_review=any(i.severity == "error" for i in issues))
