import asyncio
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.invoice import InvoiceExtraction
from app.schemas.usage import Usage
from app.services.extraction_service import PdfExtractor
from evals.metrics import SCALAR_FIELDS, Aggregate, DocScore, score_document
from evals.synth.dataset import Sample, load_split

RESULTS_DIR = Path(__file__).parent / "results"
CONCURRENCY = 3
RETRIES = 2
DIFFICULTIES = ("easy", "medium", "hard")


class OracleExtractor:
    """Returns the ground truth. Exists to prove the harness itself scores a perfect extractor at 100%."""

    def __init__(self, samples: list[Sample]) -> None:
        self._truth = {hashlib.sha1(s.pdf_bytes()).hexdigest(): s.truth for s in samples}

    async def extract(self, pdf: bytes) -> tuple[InvoiceExtraction, Usage | None]:
        return self._truth[hashlib.sha1(pdf).hexdigest()], None


@dataclass
class DocResult:
    doc_id: str
    difficulty: str
    layout: str
    locale: str
    injected_error: str | None
    score: DocScore | None = None
    usage: Usage | None = None
    error: str | None = None


async def _run_one(extractor: PdfExtractor, sample: Sample) -> DocResult:
    result = DocResult(sample.doc_id, sample.difficulty, sample.layout, sample.locale, sample.injected_error)
    for attempt in range(RETRIES + 1):
        try:
            got, usage = await extractor.extract(sample.pdf_bytes())
            result.score, result.usage = score_document(sample.truth, got), usage
            return result
        except Exception as exc:  # noqa: BLE001 - the harness records any failure, it must not crash the run
            result.error = f"{type(exc).__name__}: {exc}"
            if "PerDay" in str(exc):  # daily quota is gone, retrying only burns time
                break
            await asyncio.sleep(2 * (attempt + 1))
    return result


async def run_split(extractor: PdfExtractor, samples: list[Sample]) -> list[DocResult]:
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def guarded(sample: Sample) -> DocResult:
        async with semaphore:
            return await _run_one(extractor, sample)

    return await asyncio.gather(*(guarded(s) for s in samples))


# ---------------------------------------------------------------- reporting

def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def aggregate(results: list[DocResult]) -> Aggregate:
    agg = Aggregate()
    for r in results:
        if r.score:
            agg.add(r.score)
    return agg


def build_report(results: list[DocResult], title: str) -> str:
    scored = [r for r in results if r.score]
    failed = [r for r in results if r.error]
    overall = aggregate(results)

    def summary_row(label: str, agg: Aggregate) -> list:
        return [label, agg.docs, _pct(agg.exact_rate), _pct(agg.scalar_accuracy), _pct(agg.item_accuracy),
                f"{agg.false_alarms}", f"{agg.missed}/{agg.printed_errors}"]

    rows = [summary_row("all", overall)]
    rows += [summary_row(d, aggregate([r for r in results if r.difficulty == d])) for d in DIFFICULTIES
             if any(r.difficulty == d for r in scored)]

    md = f"# {title}\n\n"
    md += "- exact: every scored field and every line item right\n"
    md += "- fields: share of scalar fields right; items: share of line items fully right\n"
    md += "- false alarms: consistent document, but the extraction made the validator complain (an extraction error)\n"
    md += "- missed: document inconsistent as printed, but the extraction came out consistent (the model 'fixed' it)\n\n"
    md += _table(["slice", "docs", "exact", "fields", "items", "false alarms", "missed / printed errors"], rows)

    md += "\n\n## Accuracy per field\n\n"
    md += _table(["field", "accuracy"], [[f, _pct(overall.rate(overall.field_hits[f], overall.docs))] for f in SCALAR_FIELDS])

    usage = [r.usage for r in scored if r.usage]
    if usage:
        md += "\n\n## Cost and latency\n\n"
        md += _table(
            ["docs", "mean latency", "mean tokens", "total tokens"],
            [[len(usage), f"{sum(u.latency_s for u in usage) / len(usage):.1f}s",
              f"{sum(u.total_tokens for u in usage) // len(usage):,}", f"{sum(u.total_tokens for u in usage):,}"]],
        )
        costs = [u.estimated_cost_usd for u in usage if u.estimated_cost_usd is not None]
        if costs:
            md += f"\n\nEstimated cost: ${sum(costs):.4f} total, ${sum(costs) / len(costs):.4f} per document."

    imperfect = [r for r in scored if not r.score.exact]
    if imperfect:
        md += "\n\n## Documents that were not exact\n\n"
        lines = []
        for r in imperfect:
            wrong = [f for f, ok in r.score.scalars.items() if not ok]
            items = r.score.items
            detail = []
            if wrong:
                detail.append("fields: " + ", ".join(wrong))
            if items.correct != items.truth_items or items.spurious:
                detail.append(f"items: {items.correct}/{items.truth_items} right, {items.spurious} spurious")
            lines.append(f"- `{r.doc_id}` ({r.layout}, {r.locale}): " + "; ".join(detail))
        md += "\n".join(lines)

    if failed:
        md += f"\n\n## Failures ({len(failed)})\n\n" + "\n".join(f"- `{r.doc_id}`: {r.error[:200]}" for r in failed)
    return md


def save(name: str, markdown: str, results: list[DocResult], meta: dict) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (RESULTS_DIR / f"{name}.md").write_text(f"_Generated {stamp}_\n\n{markdown}\n", encoding="utf-8")
    payload = {"meta": meta, "generated": stamp, "results": [asdict(r) for r in results]}
    (RESULTS_DIR / f"{name}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
