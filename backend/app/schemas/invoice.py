from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.usage import Usage


class Party(BaseModel):
    name: str = Field(description="Legal or trading name exactly as printed on the document")
    address: str | None = Field(default=None, description="Postal address on one line, or null if not printed")
    tax_id: str | None = Field(default=None, description="VAT / tax identification number as printed, or null")


class LineItem(BaseModel):
    description: str = Field(description="Item or service description as printed")
    quantity: float = Field(description="Quantity as a plain number")
    unit_price: float = Field(description="Price of one unit as a plain number, without currency symbol")
    line_total: float = Field(description="Total for this line AS PRINTED on the document, do not recompute")


class InvoiceExtraction(BaseModel):
    """
    What the model reads from the document. Values are copied AS PRINTED, even when they look
    inconsistent: checking arithmetic is the job of `validate_invoice`, not of the model.
    """

    vendor: Party = Field(description="The party issuing the invoice (seller)")
    buyer: Party = Field(description="The party being billed (customer)")
    invoice_number: str = Field(
        description="This invoice's own number. Not an order number, a customer number, or the number of "
                    "an invoice it replaces or refers to."
    )
    issue_date: date = Field(description="Invoice date, normalised to ISO 8601 (YYYY-MM-DD)")
    due_date: date | None = Field(default=None, description="Payment due date in ISO 8601, null if not printed")
    currency: str = Field(description="ISO 4217 code, e.g. USD, EUR, GBP (derive it from symbols if needed)")
    # No max_length here: it becomes `maxItems` in the response schema, which the Gemini API rejects (HTTP 400).
    # The size limit for edited data is enforced by the validations endpoint instead.
    line_items: list[LineItem] = Field(description="Every line of the invoice, across all pages, in order")
    subtotal: float = Field(description="Sum of lines before discount and tax, as printed")
    discount_total: float = Field(default=0.0, description="Total discount as a positive number, 0 if none")
    tax_total: float = Field(description="Total tax amount, 0 if none")
    total: float = Field(description="Final amount payable as printed (grand total / amount due)")


# ---------------------------------------------------------------- validation output

Severity = Literal["error", "warning"]


class Issue(BaseModel):
    code: str = Field(description="Stable machine-readable identifier, e.g. total_mismatch")
    severity: Severity
    field: str = Field(description="Where the problem is, e.g. 'total' or 'line_items[2].line_total'")
    message: str


class ExtractionResult(BaseModel):
    """API response: the extraction plus everything the validator found."""

    extraction: InvoiceExtraction
    issues: list[Issue]
    needs_review: bool = Field(description="True when at least one error-level issue was found")
    usage: Usage | None = None
    document_id: str | None = Field(
        default=None, description="Handle for fetching page images; the document expires and can be deleted"
    )
    pages: int | None = Field(default=None, description="Number of pages of the uploaded PDF")


class ValidationResult(BaseModel):
    """Answer to re-checking values a human has edited. No model is involved."""

    issues: list[Issue]
    needs_review: bool
