"""
Scoring an extraction against ground truth.

Field level, not document level, because "mostly right" and "wrong total" are very different failures for
an invoice. A document counts as exact only when every scored field and every line is right.
"""
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.schemas.invoice import InvoiceExtraction, LineItem
from app.services.validation import validate_invoice

MONEY_TOLERANCE = 0.01
ITEM_MATCH_THRESHOLD = 0.8

SCALAR_FIELDS = (
    "invoice_number", "issue_date", "due_date", "currency",
    "vendor_name", "buyer_name", "vendor_tax_id", "buyer_tax_id",
    "subtotal", "discount_total", "tax_total", "total",
)


def _alnum(text: str | None) -> str:
    return re.sub(r"[^0-9a-zA-ZÀ-ɏ]+", "", (text or "")).casefold()


def _close(a: float, b: float, tolerance: float = MONEY_TOLERANCE) -> bool:
    return abs(a - b) <= tolerance


def score_scalars(truth: InvoiceExtraction, got: InvoiceExtraction) -> dict[str, bool]:
    return {
        "invoice_number": got.invoice_number.strip().casefold() == truth.invoice_number.strip().casefold(),
        "issue_date": got.issue_date == truth.issue_date,
        "due_date": got.due_date == truth.due_date,
        "currency": got.currency.strip().upper() == truth.currency.strip().upper(),
        "vendor_name": _alnum(got.vendor.name) == _alnum(truth.vendor.name),
        "buyer_name": _alnum(got.buyer.name) == _alnum(truth.buyer.name),
        "vendor_tax_id": _alnum(got.vendor.tax_id) == _alnum(truth.vendor.tax_id),
        "buyer_tax_id": _alnum(got.buyer.tax_id) == _alnum(truth.buyer.tax_id),
        "subtotal": _close(got.subtotal, truth.subtotal),
        "discount_total": _close(got.discount_total, truth.discount_total),
        "tax_total": _close(got.tax_total, truth.tax_total),
        "total": _close(got.total, truth.total),
    }


@dataclass
class ItemScore:
    truth_items: int
    extracted_items: int
    matched: int  # truth lines for which an extracted line with a similar description exists
    correct: int  # matched AND quantity, unit price and line total all right
    spurious: int  # extracted lines that match no truth line


def _item_numbers_correct(truth: LineItem, got: LineItem) -> bool:
    return (
        _close(got.quantity, truth.quantity, 0.001)
        and _close(got.unit_price, truth.unit_price)
        and _close(got.line_total, truth.line_total)
    )


def score_items(truth: InvoiceExtraction, got: InvoiceExtraction) -> ItemScore:
    """Greedy one-to-one matching by description similarity, so order and small typos do not matter."""
    unused = list(got.line_items)
    matched = correct = 0
    for want in truth.line_items:
        best_index, best_ratio = None, 0.0
        for i, candidate in enumerate(unused):
            ratio = SequenceMatcher(None, _alnum(want.description), _alnum(candidate.description)).ratio()
            if ratio > best_ratio:
                best_index, best_ratio = i, ratio
        if best_index is not None and best_ratio >= ITEM_MATCH_THRESHOLD:
            candidate = unused.pop(best_index)
            matched += 1
            correct += _item_numbers_correct(want, candidate)
    return ItemScore(
        truth_items=len(truth.line_items), extracted_items=len(got.line_items),
        matched=matched, correct=correct, spurious=len(unused),
    )


@dataclass
class DocScore:
    scalars: dict[str, bool]
    items: ItemScore
    exact: bool
    flagged_extraction: bool  # validator reported an error on what the model extracted
    flagged_truth: bool  # validator reports an error on the printed (true) values

    @property
    def false_alarm(self) -> bool:
        """Document is consistent but the extraction made the validator complain: an extraction error."""
        return self.flagged_extraction and not self.flagged_truth

    @property
    def missed(self) -> bool:
        """Document is inconsistent as printed but the extraction came out consistent."""
        return self.flagged_truth and not self.flagged_extraction


def score_document(truth: InvoiceExtraction, got: InvoiceExtraction) -> DocScore:
    scalars = score_scalars(truth, got)
    items = score_items(truth, got)
    exact = all(scalars.values()) and items.correct == items.truth_items and items.spurious == 0
    has_error = lambda inv: any(i.severity == "error" for i in validate_invoice(inv))  # noqa: E731
    return DocScore(scalars, items, exact, has_error(got), has_error(truth))


# ---------------------------------------------------------------- aggregation

@dataclass
class Aggregate:
    docs: int = 0
    exact: int = 0
    field_hits: dict[str, int] = field(default_factory=lambda: {name: 0 for name in SCALAR_FIELDS})
    truth_items: int = 0
    items_matched: int = 0
    items_correct: int = 0
    spurious_items: int = 0
    false_alarms: int = 0
    missed: int = 0
    printed_errors: int = 0  # docs whose printed values are inconsistent

    def add(self, score: DocScore) -> None:
        self.docs += 1
        self.exact += score.exact
        for name, ok in score.scalars.items():
            self.field_hits[name] += ok
        self.truth_items += score.items.truth_items
        self.items_matched += score.items.matched
        self.items_correct += score.items.correct
        self.spurious_items += score.items.spurious
        self.false_alarms += score.false_alarm
        self.missed += score.missed
        self.printed_errors += score.flagged_truth

    def rate(self, hits: int, total: int) -> float:
        return hits / total if total else 0.0

    @property
    def exact_rate(self) -> float:
        return self.rate(self.exact, self.docs)

    @property
    def scalar_accuracy(self) -> float:
        return self.rate(sum(self.field_hits.values()), self.docs * len(SCALAR_FIELDS))

    @property
    def item_accuracy(self) -> float:
        return self.rate(self.items_correct, self.truth_items)
