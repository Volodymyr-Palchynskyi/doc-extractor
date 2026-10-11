import logging
import time
from typing import Any, Protocol

from google import genai
from google.genai import types

from app.core.config import settings
from app.schemas.invoice import ExtractionResult, InvoiceExtraction
from app.schemas.usage import Usage
from app.services.validation import validate_invoice

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    "You extract structured data from invoices. Read the whole document, every page. "
    "Copy numbers AS PRINTED, even if they look wrong or do not add up: never correct, recompute or "
    "'fix' them, a separate validator checks the arithmetic. "
    "Numbers: output plain numbers with a dot as decimal separator and no thousands separators, whatever "
    "the document's convention (1.234,56 means 1234.56; 1 234,56 means 1234.56; 1,234.56 means 1234.56). "
    "Dates: output ISO 8601 (YYYY-MM-DD); use the document's language, currency and other cues to decide "
    "whether 03/04/2026 is day-first or month-first. "
    "Currency: ISO 4217 code, derived from symbols if necessary. "
    "The invoice number is the number of THIS invoice. Do not use purchase order numbers, customer or "
    "account numbers, bank details, or the number of another invoice that this one replaces or refers to. "
    "Include every line item across all pages and nothing that is not a line item (no subtotal, tax or "
    "total rows). Discount is a positive number, 0 when absent; tax is 0 when absent. "
    "Party tax IDs: return the identifier itself, without a label such as 'EIN' or 'VAT No.', but keep a "
    "country prefix that is part of the number (DE123456789). "
    "Use null for optional fields that are not printed; never invent values."
)


class PdfExtractor(Protocol):
    """Anything that can turn PDF bytes into an InvoiceExtraction. Evals and tests swap implementations."""

    async def extract(self, pdf: bytes) -> tuple[InvoiceExtraction, Usage | None]: ...


class GeminiExtractor:
    """Sends the PDF itself to a multimodal model, so layout and tables are seen, not flattened to text."""

    def __init__(self, instruction: str = SYSTEM_INSTRUCTION) -> None:
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured in settings or .env file.")
        self.instruction = instruction  # overridable so evals can run prompt ablations
        self.model = settings.GEMINI_MODEL
        self._client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=settings.GEMINI_TIMEOUT_S * 1000),
        )

    async def extract(self, pdf: bytes) -> tuple[InvoiceExtraction, Usage | None]:
        started = time.perf_counter()
        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_bytes(data=pdf, mime_type="application/pdf"),
                "Extract the invoice.",
            ],
            config=types.GenerateContentConfig(
                system_instruction=self.instruction,
                response_mime_type="application/json",
                response_schema=InvoiceExtraction,
                temperature=0.0,
            ),
        )
        if not response.text:
            raise RuntimeError("Gemini returned an empty response.")
        invoice = InvoiceExtraction.model_validate_json(response.text)
        return invoice, self._usage(response.usage_metadata, started)

    def _usage(self, metadata: Any, started: float) -> Usage | None:
        if metadata is None:
            return None
        input_tokens = metadata.prompt_token_count or 0
        output_tokens = metadata.candidates_token_count or 0
        thinking_tokens = metadata.thoughts_token_count or 0
        cost = None
        if settings.PRICE_INPUT_PER_MTOK or settings.PRICE_OUTPUT_PER_MTOK:
            cost = round(
                (input_tokens * settings.PRICE_INPUT_PER_MTOK
                 + (output_tokens + thinking_tokens) * settings.PRICE_OUTPUT_PER_MTOK) / 1_000_000,
                5,
            )
        return Usage(
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_tokens,
            total_tokens=metadata.total_token_count or input_tokens + output_tokens + thinking_tokens,
            latency_s=round(time.perf_counter() - started, 1),
            estimated_cost_usd=cost,
        )


async def extract_and_validate(extractor: PdfExtractor, pdf: bytes) -> ExtractionResult:
    invoice, usage = await extractor.extract(pdf)
    issues = validate_invoice(invoice)
    if usage:
        logger.info("extraction usage: %s", usage.model_dump_json())
    return ExtractionResult(
        extraction=invoice,
        issues=issues,
        needs_review=any(i.severity == "error" for i in issues),
        usage=usage,
    )
