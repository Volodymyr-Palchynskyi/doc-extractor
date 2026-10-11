"""Locale rules for how an invoice prints dates and numbers, and the labels it uses."""
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£"}


@dataclass(frozen=True)
class Locale:
    code: str
    date_formats: tuple[str, ...]
    decimal: str
    thousands: str
    currencies: tuple[str, ...]
    symbol_after: bool
    labels: dict[str, object]  # str, or tuple[str, ...] for synonyms
    vendor_suffixes: tuple[str, ...]
    cities: tuple[tuple[str, str], ...]  # (city, postcode)
    streets: tuple[str, ...]
    tax_id_format: str  # {} is filled with digits; the result is the identifier itself
    tax_id_label: str  # printed before the identifier but NOT part of it (e.g. 'EIN'); '' if none
    invoice_number_formats: tuple[str, ...]
    item_descriptions: tuple[str, ...]


# Month *names* depend on the process locale in strftime, so non-English locales use numeric dates only.
EN_US = Locale(
    code="en_US",
    date_formats=("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"),
    decimal=".", thousands=",",
    currencies=("USD",),
    symbol_after=False,
    labels={
        "invoice": "INVOICE", "invoice_number": "Invoice No.", "issue_date": "Invoice date",
        "due_date": "Due date", "bill_to": "Bill to", "from": "From", "description": "Description",
        "quantity": "Qty", "unit_price": "Unit price", "amount": "Amount", "subtotal": "Subtotal",
        "discount": "Discount", "tax": "Sales tax", "total": ("Total", "Amount due", "Balance due", "Grand total"),
        "page": "Page", "of": "of", "po_number": "PO number", "customer_number": "Customer ID",
        "replaces": "This invoice replaces invoice", "bank": "Bank details", "terms": "Payment terms",
        "terms_text": "Payment is due within the period stated above. Late payments may incur interest.",
    },
    vendor_suffixes=("LLC", "Inc.", "Corp.", "Co."),
    cities=(("Austin, TX", "78701"), ("Denver, CO", "80202"), ("Boston, MA", "02110"), ("Seattle, WA", "98101")),
    streets=("Main Street", "Market Avenue", "Oak Road", "Lakeview Drive"),
    tax_id_format="{}",
    tax_id_label="EIN",
    invoice_number_formats=("INV-2026-{:04d}", "{:06d}", "INV{:05d}"),
    item_descriptions=(
        "Backend development (hours)", "UX design workshop", "Cloud hosting, monthly", "Security audit",
        "Technical support plan", "Data migration", "API integration", "Mobile app maintenance",
        "27-inch monitor", "USB-C docking station", "Ergonomic keyboard", "Annual software license",
    ),
)

EN_GB = Locale(
    code="en_GB",
    date_formats=("%d %B %Y", "%d %b %Y", "%d/%m/%Y"),
    decimal=".", thousands=",",
    currencies=("GBP",),
    symbol_after=False,
    labels={**EN_US.labels, "tax": "VAT", "customer_number": "Account no.", "po_number": "Purchase order"},
    vendor_suffixes=("Ltd", "PLC", "LLP", "& Sons"),
    cities=(("London", "EC1A 1BB"), ("Manchester", "M1 1AE"), ("Bristol", "BS1 4DJ"), ("Leeds", "LS1 4AP")),
    streets=("High Street", "Station Road", "Church Lane", "Victoria Street"),
    tax_id_format="GB {}",
    tax_id_label="",
    invoice_number_formats=("INV-{:05d}", "SI-2026-{:04d}", "{:06d}"),
    item_descriptions=EN_US.item_descriptions,
)

DE_DE = Locale(
    code="de_DE",
    date_formats=("%d.%m.%Y",),
    decimal=",", thousands=".",
    currencies=("EUR",),
    symbol_after=True,
    labels={
        "invoice": "RECHNUNG", "invoice_number": "Rechnungsnummer", "issue_date": "Rechnungsdatum",
        "due_date": "Fälligkeitsdatum", "bill_to": "Rechnungsempfänger", "from": "Absender",
        "description": "Bezeichnung", "quantity": "Menge", "unit_price": "Einzelpreis", "amount": "Gesamt",
        "subtotal": "Zwischensumme", "discount": "Rabatt", "tax": "MwSt.",
        "total": ("Gesamtbetrag", "Rechnungsbetrag", "Zu zahlen"),
        "page": "Seite", "of": "von", "po_number": "Bestellnummer", "customer_number": "Kundennummer",
        "replaces": "Diese Rechnung ersetzt Rechnung", "bank": "Bankverbindung", "terms": "Zahlungsbedingungen",
        "terms_text": "Zahlbar innerhalb der angegebenen Frist. Bei Verzug werden Zinsen berechnet.",
    },
    vendor_suffixes=("GmbH", "AG", "KG", "GmbH & Co. KG"),
    cities=(("Berlin", "10115"), ("München", "80331"), ("Hamburg", "20095"), ("Köln", "50667")),
    streets=("Hauptstraße", "Bahnhofstraße", "Gartenweg", "Schulstraße"),
    tax_id_format="DE{}",
    tax_id_label="",
    invoice_number_formats=("RE-2026-{:04d}", "{:06d}", "R{:05d}"),
    item_descriptions=(
        "Beratungsleistung (Stunden)", "Softwarelizenz jährlich", "Wartung und Support", "Schulung vor Ort",
        "Datenmigration", "Systemintegration", "Hosting monatlich", "Sicherheitsprüfung",
        "Monitor 27 Zoll", "Dockingstation USB-C", "Ergonomische Tastatur", "Installation und Einrichtung",
    ),
)

FR_FR = Locale(
    code="fr_FR",
    date_formats=("%d/%m/%Y", "%d-%m-%Y"),
    decimal=",", thousands=" ",
    currencies=("EUR",),
    symbol_after=True,
    labels={
        "invoice": "FACTURE", "invoice_number": "Numéro de facture", "issue_date": "Date de facture",
        "due_date": "Date d'échéance", "bill_to": "Facturé à", "from": "Émetteur",
        "description": "Désignation", "quantity": "Quantité", "unit_price": "Prix unitaire",
        "amount": "Montant", "subtotal": "Total HT", "discount": "Remise", "tax": "TVA",
        "total": ("Total TTC", "Net à payer", "Montant dû"),
        "page": "Page", "of": "sur", "po_number": "Bon de commande", "customer_number": "Réf. client",
        "replaces": "Cette facture remplace la facture", "bank": "Coordonnées bancaires",
        "terms": "Conditions de paiement",
        "terms_text": "Paiement à réception dans le délai indiqué. Pénalités de retard applicables.",
    },
    vendor_suffixes=("SARL", "SAS", "SA", "& Fils"),
    cities=(("Paris", "75001"), ("Lyon", "69001"), ("Marseille", "13001"), ("Toulouse", "31000")),
    streets=("rue de la Paix", "avenue des Champs", "boulevard Voltaire", "rue du Commerce"),
    tax_id_format="FR{}",
    tax_id_label="",
    invoice_number_formats=("FA-2026-{:04d}", "{:06d}", "F{:05d}"),
    item_descriptions=(
        "Prestation de conseil (heures)", "Licence logicielle annuelle", "Maintenance et support",
        "Formation sur site", "Migration de données", "Intégration de systèmes", "Hébergement mensuel",
        "Audit de sécurité", "Écran 27 pouces", "Station d'accueil USB-C", "Clavier ergonomique",
        "Installation et configuration",
    ),
)

LOCALES = {loc.code: loc for loc in (EN_US, EN_GB, DE_DE, FR_FR)}


def to_decimal(value: float | Decimal | int) -> Decimal:
    return Decimal(str(value))


def round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_number(value: float, loc: Locale, decimals: int = 2) -> str:
    """1234.5 -> '1,234.50' (en) / '1.234,50' (de) / '1 234,50' (fr)."""
    q = Decimal(1).scaleb(-decimals)
    text = f"{to_decimal(value).quantize(q, rounding=ROUND_HALF_UP):,.{decimals}f}"
    integer, _, fraction = text.partition(".")
    integer = integer.replace(",", loc.thousands)
    return integer + (loc.decimal + fraction if fraction else "")


def format_quantity(value: float, loc: Locale) -> str:
    if float(value).is_integer():
        return str(int(value))
    return format_number(value, loc, decimals=2).rstrip("0").rstrip(loc.decimal)


def format_money(value: float, currency: str, loc: Locale, style: str) -> str:
    """style: 'symbol' (locale-typical placement), 'code' (e.g. '1,234.50 USD')."""
    number = format_number(value, loc)
    if style == "code":
        return f"{number} {currency}"
    symbol = CURRENCY_SYMBOLS[currency]
    return f"{number} {symbol}" if loc.symbol_after else f"{symbol}{number}"


def format_date(value: date, fmt: str) -> str:
    # %d with a leading zero is fine; strftime month names are English under the default C locale.
    return value.strftime(fmt)
