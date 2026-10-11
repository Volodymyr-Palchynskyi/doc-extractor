from datetime import date

from app.schemas.invoice import InvoiceExtraction, LineItem, Party
from evals.metrics import Aggregate, score_document, score_items, score_scalars


def make(**overrides) -> InvoiceExtraction:
    base = dict(
        vendor=Party(name="Acme GmbH", tax_id="DE123456789"),
        buyer=Party(name="Beta Ltd", tax_id=None),
        invoice_number="INV-001",
        issue_date=date(2026, 3, 1),
        due_date=date(2026, 3, 31),
        currency="EUR",
        line_items=[
            LineItem(description="Backend development (hours)", quantity=2, unit_price=50.0, line_total=100.0),
            LineItem(description="Cloud hosting, monthly", quantity=1, unit_price=20.0, line_total=20.0),
        ],
        subtotal=120.0, discount_total=0.0, tax_total=22.8, total=142.8,
    )
    base.update(overrides)
    return InvoiceExtraction(**base)


def test_identical_extraction_is_exact():
    score = score_document(make(), make())

    assert score.exact and all(score.scalars.values())
    assert score.items.correct == 2 and score.items.spurious == 0
    assert not score.false_alarm and not score.missed


def test_scalar_tolerances_and_normalisation():
    got = make(
        invoice_number=" inv-001 ", currency="eur", vendor=Party(name="ACME  GmbH.", tax_id="DE 123 456 789"),
        total=142.805,
    )
    assert all(score_scalars(make(), got).values())


def test_each_wrong_scalar_is_reported_individually():
    got = make(issue_date=date(2026, 1, 3), total=100.0, invoice_number="INV-002")
    wrong = {name for name, ok in score_scalars(make(), got).items() if not ok}

    assert wrong == {"issue_date", "total", "invoice_number"}


def test_due_date_missing_vs_present_counts_as_wrong():
    assert not score_scalars(make(), make(due_date=None))["due_date"]
    assert score_scalars(make(due_date=None), make(due_date=None))["due_date"]


def test_items_match_regardless_of_order_and_small_typos():
    got = make(line_items=[
        LineItem(description="Cloud hosting monthly", quantity=1, unit_price=20.0, line_total=20.0),
        LineItem(description="Backend development (hours)", quantity=2, unit_price=50.0, line_total=100.0),
    ])
    score = score_items(make(), got)

    assert (score.matched, score.correct, score.spurious) == (2, 2, 0)


def test_missing_wrong_and_extra_items_are_distinguished():
    got = make(line_items=[
        LineItem(description="Backend development (hours)", quantity=2, unit_price=50.0, line_total=99.0),  # wrong total
        LineItem(description="Something nobody printed", quantity=1, unit_price=5.0, line_total=5.0),  # spurious
    ])
    score = score_items(make(), got)

    assert score.matched == 1 and score.correct == 0 and score.spurious == 1
    assert not score_document(make(), got).exact


def test_one_extracted_line_cannot_match_two_truth_lines():
    truth = make(line_items=[
        LineItem(description="Hosting", quantity=1, unit_price=10.0, line_total=10.0),
        LineItem(description="Hosting", quantity=1, unit_price=10.0, line_total=10.0),
    ])
    got = make(line_items=[LineItem(description="Hosting", quantity=1, unit_price=10.0, line_total=10.0)])

    assert score_items(truth, got).matched == 1


def test_false_alarm_when_extraction_error_breaks_consistent_document():
    # truth is consistent; the model misread the total, so the validator complains
    score = score_document(make(), make(total=999.0))

    assert score.false_alarm and not score.missed


def test_missed_when_printed_error_disappears_from_extraction():
    printed_wrong = make(total=500.0)  # the document itself is inconsistent
    score = score_document(printed_wrong, make())  # the model "helpfully" produced a consistent total

    assert score.missed and not score.false_alarm


def test_faithfully_extracted_printed_error_is_not_counted_against_the_model():
    printed_wrong = make(total=500.0)
    score = score_document(printed_wrong, printed_wrong)

    assert score.exact and not score.false_alarm and not score.missed


def test_aggregate_rates():
    agg = Aggregate()
    agg.add(score_document(make(), make()))
    agg.add(score_document(make(), make(total=1.0)))

    assert agg.docs == 2 and agg.exact_rate == 0.5
    assert agg.field_hits["total"] == 1 and agg.field_hits["currency"] == 2
    assert agg.false_alarms == 1 and agg.printed_errors == 0
