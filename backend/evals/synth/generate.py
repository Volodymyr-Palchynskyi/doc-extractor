"""
Synthetic invoices with exact ground truth.

Every document is generated from a seed, so the dataset is reproducible and the labels are right by
construction (no human labelling, no real personal data). Difficulty comes from layout, locale (date and
number conventions), length (multi-page), distractor numbers and, in some documents, arithmetic errors that
are really printed on the page, as in real life. The ground truth stores what is PRINTED.
"""
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from app.schemas.invoice import InvoiceExtraction, LineItem, Party
from evals.synth.formats import LOCALES, Locale, round_money, to_decimal

DIFFICULTIES = ("easy", "medium", "hard")
LAYOUTS = ("classic", "modern", "minimal")

VENDOR_PREFIXES = ("Northwind", "Brightside", "Kestrel", "Orion", "Maple", "Bluefin", "Harbor", "Summit",
                   "Atlas", "Quartz", "Lumen", "Fjord", "Cobalt", "Juniper", "Meridian", "Sable")
VENDOR_NOUNS = ("Traders", "Logistics", "Systems", "Consulting", "Digital", "Supplies", "Engineering",
                "Solutions", "Works", "Analytics", "Partners", "Labs")
TAX_RATES = {"en_US": (0.0, 6.25, 8.25), "en_GB": (0.0, 5.0, 20.0), "de_DE": (7.0, 19.0), "fr_FR": (5.5, 10.0, 20.0)}


@dataclass(frozen=True)
class Difficulty:
    locales: tuple[str, ...]
    layouts: tuple[str, ...]
    items: tuple[int, int]
    discount_chance: float
    missing_due_chance: float
    distractors: bool
    hard_distractors: bool  # "replaces invoice X", bank details, long terms
    error_chance: float


CONFIG = {
    "easy": Difficulty(("en_US", "en_GB"), ("classic", "modern"), (1, 5), 0.0, 0.0, False, False, 0.0),
    "medium": Difficulty(("en_US", "en_GB", "de_DE", "fr_FR"), LAYOUTS, (4, 12), 0.4, 0.2, True, False, 0.1),
    "hard": Difficulty(("en_US", "en_GB", "de_DE", "fr_FR"), LAYOUTS, (14, 32), 0.6, 0.2, True, True, 0.3),
}


@dataclass(frozen=True)
class Distractors:
    po_number: str | None = None
    customer_number: str | None = None
    replaces: str | None = None
    iban: str | None = None
    bic: str | None = None
    long_terms: bool = False


@dataclass(frozen=True)
class SyntheticInvoice:
    doc_id: str
    split: str
    difficulty: str
    layout: str
    locale: str
    date_format: str
    money_style: str  # 'symbol' or 'code'
    total_label: str
    tax_rate: float
    discount_rate: float
    injected_error: str | None
    distractors: Distractors
    truth: InvoiceExtraction = field(compare=False)

    @property
    def loc(self) -> Locale:
        return LOCALES[self.locale]


def _party(rng: random.Random, loc: Locale, taken: set[str]) -> Party:
    while True:
        name = f"{rng.choice(VENDOR_PREFIXES)} {rng.choice(VENDOR_NOUNS)} {rng.choice(loc.vendor_suffixes)}"
        if name not in taken:
            taken.add(name)
            break
    city, postcode = rng.choice(loc.cities)
    number = rng.randint(1, 180)
    street = rng.choice(loc.streets)
    # Street/number order differs by country; the address is just printed text to the extractor.
    line = f"{street} {number}, {postcode} {city}" if loc.code in ("de_DE",) else f"{number} {street}, {city} {postcode}"
    digits = "".join(str(rng.randint(0, 9)) for _ in range(9))
    return Party(name=name, address=line, tax_id=loc.tax_id_format.format(digits) if rng.random() < 0.8 else None)


def _line_items(rng: random.Random, loc: Locale, count: int) -> list[LineItem]:
    """Unique descriptions (a numbered variant when the pool runs out) so lines can be matched unambiguously."""
    pool = loc.item_descriptions
    items = []
    for n in range(count):
        base_index = n % len(pool)
        description = pool[base_index] if n < len(pool) else f"{pool[base_index]} - ref {n:02d}"
        is_hardware = base_index >= len(pool) - 4
        quantity = rng.choice((0.5, 1.5, 2.25, 7.5)) if rng.random() < 0.15 and not is_hardware else rng.randint(1, 24 if not is_hardware else 6)
        unit_price = round(rng.uniform(49, 1200) if is_hardware else rng.uniform(35, 260), 2)
        line_total = round_money(to_decimal(quantity) * to_decimal(unit_price))
        items.append(LineItem(description=description, quantity=quantity, unit_price=unit_price, line_total=float(line_total)))
    rng.shuffle(items)
    return items


def _inject_error(rng: random.Random, invoice: InvoiceExtraction) -> tuple[InvoiceExtraction, str]:
    """Change a PRINTED number so the document is internally inconsistent."""
    kind = rng.choice(("total_off", "line_total_off", "subtotal_off"))
    delta = round(rng.uniform(5, 250), 2)
    data = invoice.model_copy(deep=True)
    if kind == "total_off":
        data.total = round(data.total + delta, 2)
    elif kind == "subtotal_off":
        data.subtotal = round(data.subtotal + delta, 2)
    else:
        idx = rng.randrange(len(data.line_items))
        data.line_items[idx].line_total = round(data.line_items[idx].line_total + delta, 2)
    return data, kind


def make_invoice(split: str, difficulty: str, index: int) -> SyntheticInvoice:
    rng = random.Random(f"{split}-{difficulty}-{index}")
    cfg = CONFIG[difficulty]

    loc = LOCALES[rng.choice(cfg.locales)]
    layout = rng.choice(cfg.layouts)
    currency = rng.choice(loc.currencies)
    money_style = "code" if rng.random() < 0.2 else "symbol"

    taken: set[str] = set()
    vendor, buyer = _party(rng, loc, taken), _party(rng, loc, taken)

    items = _line_items(rng, loc, rng.randint(*cfg.items))
    subtotal = sum((to_decimal(i.line_total) for i in items), Decimal("0"))
    discount_rate = rng.choice((5.0, 10.0, 15.0)) if rng.random() < cfg.discount_chance else 0.0
    discount = round_money(subtotal * to_decimal(discount_rate) / 100)
    tax_rate = rng.choice(TAX_RATES[loc.code])
    tax = round_money((subtotal - discount) * to_decimal(tax_rate) / 100)
    total = subtotal - discount + tax

    issue = date(2026, 1, 1) + timedelta(days=rng.randint(0, 360))
    due = None if rng.random() < cfg.missing_due_chance else issue + timedelta(days=rng.choice((14, 30, 45, 60)))
    number = rng.choice(loc.invoice_number_formats).format(rng.randint(1, 9999))

    invoice = InvoiceExtraction(
        vendor=vendor, buyer=buyer, invoice_number=number, issue_date=issue, due_date=due, currency=currency,
        line_items=items, subtotal=float(subtotal), discount_total=float(discount), tax_total=float(tax),
        total=float(total),
    )

    injected = None
    if rng.random() < cfg.error_chance:
        invoice, injected = _inject_error(rng, invoice)

    distractors = Distractors()
    if cfg.distractors:
        distractors = Distractors(
            po_number=f"PO-{rng.randint(10000, 99999)}",
            customer_number=f"C-{rng.randint(1000, 99999)}",
            replaces=rng.choice(loc.invoice_number_formats).format(rng.randint(1, 9999)) if cfg.hard_distractors and rng.random() < 0.5 else None,
            iban=f"{loc.code[-2:]}{rng.randint(10, 99)}" + "".join(str(rng.randint(0, 9)) for _ in range(18)) if cfg.hard_distractors or rng.random() < 0.5 else None,
            bic="".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(8)) if cfg.hard_distractors else None,
            long_terms=cfg.hard_distractors,
        )
        if distractors.replaces == number:  # never let the distractor equal the real number
            distractors = Distractors(**{**distractors.__dict__, "replaces": None})

    total_label = rng.choice(loc.labels["total"])
    return SyntheticInvoice(
        doc_id=f"{split}-{difficulty}-{index:02d}",
        split=split, difficulty=difficulty, layout=layout, locale=loc.code,
        date_format=rng.choice(loc.date_formats[:2] if difficulty == "easy" and len(loc.date_formats) > 2 else loc.date_formats), money_style=money_style, total_label=total_label,
        tax_rate=tax_rate, discount_rate=discount_rate, injected_error=injected,
        distractors=distractors, truth=invoice,
    )
