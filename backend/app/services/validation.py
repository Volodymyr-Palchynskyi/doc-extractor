"""
Deterministic checks on an extracted invoice.

The model copies numbers off the page; this module decides whether they add up. A failing check means
"a human should look": either the document is wrong or the extraction is, and in both cases trusting the
numbers blindly would be a mistake. Money is compared as Decimal at cent precision, never as raw floats.
"""
from decimal import ROUND_HALF_UP, Decimal

from app.schemas.invoice import InvoiceExtraction, Issue

# Rounding differences between how an invoice system rounds and how we recompute are normal.
TOLERANCE = Decimal("0.01")

# Not exhaustive on purpose: an unknown but well-formed code is a warning, not an error.
KNOWN_CURRENCIES = {
    "USD", "EUR", "GBP", "CHF", "JPY", "CNY", "CAD", "AUD", "NZD", "SEK", "NOK", "DKK", "PLN", "CZK",
    "HUF", "RON", "UAH", "TRY", "INR", "BRL", "MXN", "ZAR", "SGD", "HKD", "AED",
}


def money(value: float) -> Decimal:
    """Float to cents via its shortest repr, so 0.1 + 0.2 style noise does not leak in."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCE


def validate_invoice(invoice: InvoiceExtraction) -> list[Issue]:
    issues: list[Issue] = []

    def error(code: str, field: str, message: str) -> None:
        issues.append(Issue(code=code, severity="error", field=field, message=message))

    def warning(code: str, field: str, message: str) -> None:
        issues.append(Issue(code=code, severity="warning", field=field, message=message))

    if not invoice.invoice_number.strip():
        error("missing_invoice_number", "invoice_number", "Invoice number is empty.")
    if not invoice.line_items:
        error("no_line_items", "line_items", "No line items were extracted.")

    # --- currency
    code = invoice.currency.strip()
    if not (len(code) == 3 and code.isalpha() and code.isupper()):
        error("invalid_currency", "currency", f"'{invoice.currency}' is not a three-letter ISO 4217 code.")
    elif code not in KNOWN_CURRENCIES:
        warning("unknown_currency", "currency", f"'{code}' is well-formed but not a commonly used currency code.")

    # --- dates
    if invoice.due_date is not None and invoice.due_date < invoice.issue_date:
        error("due_before_issue", "due_date", f"Due date {invoice.due_date} is before issue date {invoice.issue_date}.")

    # --- amounts must not be negative (credit notes are a different document type)
    for name in ("subtotal", "discount_total", "tax_total", "total"):
        if getattr(invoice, name) < 0:
            error("negative_amount", name, f"{name} is negative ({getattr(invoice, name)}).")

    # --- every line: quantity * unit price = line total
    for i, item in enumerate(invoice.line_items):
        expected = (Decimal(str(item.quantity)) * Decimal(str(item.unit_price))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if not _close(money(item.line_total), expected):
            error(
                "line_total_mismatch",
                f"line_items[{i}].line_total",
                f"{item.quantity} x {item.unit_price} = {expected}, but the line total is {money(item.line_total)}.",
            )

    # --- subtotal = sum of lines
    if invoice.line_items:
        lines_sum = sum((money(item.line_total) for item in invoice.line_items), Decimal("0"))
        if not _close(money(invoice.subtotal), lines_sum):
            error(
                "subtotal_mismatch",
                "subtotal",
                f"Line totals add up to {lines_sum}, but the subtotal is {money(invoice.subtotal)}.",
            )

    # --- total = subtotal - discount + tax
    expected_total = money(invoice.subtotal) - money(invoice.discount_total) + money(invoice.tax_total)
    if not _close(money(invoice.total), expected_total):
        error(
            "total_mismatch",
            "total",
            f"Subtotal {money(invoice.subtotal)} - discount {money(invoice.discount_total)} + tax "
            f"{money(invoice.tax_total)} = {expected_total}, but the total is {money(invoice.total)}.",
        )

    return issues
