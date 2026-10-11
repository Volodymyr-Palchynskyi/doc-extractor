"""Build, store and load the synthetic datasets (PDF files plus a truth.jsonl per split)."""
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from app.schemas.invoice import InvoiceExtraction
from evals.synth.generate import SyntheticInvoice, make_invoice
from evals.synth.render import render_pdf

DATASET_DIR = Path(__file__).parent.parent / "dataset"

# `dev` is for building and debugging the extractor. `test` is sealed: run it once per configuration you
# want to report, never to iterate (see evals/README.md).
SPLITS: dict[str, dict[str, int]] = {
    "dev": {"easy": 8, "medium": 10, "hard": 10},
    "test": {"easy": 8, "medium": 10, "hard": 10},
}


@dataclass(frozen=True)
class Sample:
    doc_id: str
    split: str
    difficulty: str
    layout: str
    locale: str
    injected_error: str | None
    pdf_path: Path
    truth: InvoiceExtraction

    def pdf_bytes(self) -> bytes:
        return self.pdf_path.read_bytes()


def iter_synthetic(split: str) -> Iterator[SyntheticInvoice]:
    for difficulty, count in SPLITS[split].items():
        for index in range(count):
            yield make_invoice(split, difficulty, index)


def build_split(split: str, out_dir: Path = DATASET_DIR) -> int:
    target = out_dir / split
    target.mkdir(parents=True, exist_ok=True)
    for stale in target.glob("*.pdf"):
        stale.unlink()

    lines = []
    for inv in iter_synthetic(split):
        (target / f"{inv.doc_id}.pdf").write_bytes(render_pdf(inv))
        lines.append(json.dumps({
            "doc_id": inv.doc_id, "split": inv.split, "difficulty": inv.difficulty, "layout": inv.layout,
            "locale": inv.locale, "injected_error": inv.injected_error,
            "truth": inv.truth.model_dump(mode="json"),
        }, ensure_ascii=False))
    (target / "truth.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def load_split(split: str, dataset_dir: Path = DATASET_DIR) -> list[Sample]:
    folder = dataset_dir / split
    samples = []
    for line in (folder / "truth.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        samples.append(Sample(
            doc_id=row["doc_id"], split=row["split"], difficulty=row["difficulty"], layout=row["layout"],
            locale=row["locale"], injected_error=row["injected_error"], pdf_path=folder / f"{row['doc_id']}.pdf",
            truth=InvoiceExtraction.model_validate(row["truth"]),
        ))
    return samples
