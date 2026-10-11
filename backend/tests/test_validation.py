from datetime import date

import pytest

from app.schemas.invoice import InvoiceExtraction, LineItem, Party
from app.services.validation import money, validate_invoice


def invoice(**overrides) -> InvoiceExtraction:
    """A correct invoice: 2 x 50.00 + 1 x 19.99 = 119.99, 10% discount, 19% tax."""
    base = dict(
        vendor=Party(name="Acme GmbH"),
        buyer=Party(name="Beta Ltd"),
        invoice_number="INV-001",
        issue_date=date(2026, 3, 1),
        due_date=date(2026, 3, 31),
        currency="EUR",
        line_items=[
            LineItem(description="Widget", quantity=2, unit_price=50.0, line_total=100.0),
            LineItem(description="Gadget", quantity=1, unit_price=19.99, line_total=19.99),
        ],
        subtotal=119.99,
        discount_total=12.0,
        tax_total=20.52,
        total=128.51,
    )
    base.update(overrides)
    return InvoiceExtraction(**base)


def codes(inv: InvoiceExtraction) -> set[str]:
    return {i.code for i in validate_invoice(inv)}


def test_consistent_invoice_has_no_issues():
    assert validate_invoice(invoice()) == []


def test_line_total_mismatch_is_located():
    bad = invoice(line_items=[
        LineItem(description="Widget", quantity=2, unit_price=50.0, line_total=90.0),
        LineItem(description="Gadget", quantity=1, unit_price=19.99, line_total=19.99),
    ])
    issues = [i for i in validate_invoice(bad) if i.code == "line_total_mismatch"]

    assert [i.field for i in issues] == ["line_items[0].line_total"]


def test_subtotal_and_total_mismatches():
    assert "subtotal_mismatch" in codes(invoice(subtotal=130.0))
    assert "total_mismatch" in codes(invoice(total=150.0))


def test_one_cent_rounding_difference_is_tolerated():
    assert codes(invoice(total=128.52)) == set()
    assert "total_mismatch" in codes(invoice(total=128.53))


def test_float_noise_does_not_cause_false_alarms():
    # 0.1 + 0.2 != 0.3 in binary floats; the validator works on cents.
    inv = invoice(
        line_items=[
            LineItem(description="a", quantity=1, unit_price=0.1, line_total=0.1),
            LineItem(description="b", quantity=1, unit_price=0.2, line_total=0.2),
        ],
        subtotal=0.3, discount_total=0.0, tax_total=0.0, total=0.3,
    )
    assert validate_invoice(inv) == []


def test_due_date_before_issue_date():
    assert "due_before_issue" in codes(invoice(due_date=date(2026, 2, 1)))
    assert "due_before_issue" not in codes(invoice(due_date=None))


@pytest.mark.parametrize("currency, expected", [("eur", {"invalid_currency"}), ("EURO", {"invalid_currency"}),
                                                ("XYZ", {"unknown_currency"}), ("EUR", set())])
def test_currency_checks(currency, expected):
    assert codes(invoice(currency=currency)) == expected


def test_severity_distinguishes_review_from_note():
    by_code = {i.code: i.severity for i in validate_invoice(invoice(currency="XYZ", total=1.0))}

    assert by_code["unknown_currency"] == "warning"
    assert by_code["total_mismatch"] == "error"


def test_empty_invoice_number_and_no_lines():
    got = codes(invoice(invoice_number="  ", line_items=[], subtotal=0.0, discount_total=0.0, tax_total=0.0, total=0.0))
    assert {"missing_invoice_number", "no_line_items"} <= got


def test_negative_amounts_are_errors():
    assert "negative_amount" in codes(invoice(tax_total=-1.0))


def test_money_rounds_half_up_not_bankers():
    assert str(money(2.675)) == "2.68"  # Python's round(2.675, 2) gives 2.67
