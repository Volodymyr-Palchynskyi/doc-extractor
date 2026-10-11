"""
Demo mode: replay recorded model output for a few bundled sample documents.

It exists so the whole application, UI included, can be tried without an API key or quota. The recorded
extractions are REAL outputs of the model on these exact PDFs (see app/demo/README.md), not hand-written
answers, so the demo shows the real behaviour, including any mistake the model made.
"""
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.schemas.invoice import InvoiceExtraction
from app.schemas.usage import Usage

DEMO_DIR = Path(__file__).parent.parent / "demo"


class NotASampleError(ValueError):
    """Raised in demo mode for a document that was not recorded."""


@dataclass(frozen=True)
class Sample:
    id: str
    title: str
    description: str
    file_name: str
    pdf: bytes
    extraction: InvoiceExtraction
    usage: Usage | None


def load_samples(directory: Path = DEMO_DIR) -> list[Sample]:
    index = directory / "samples.json"
    if not index.exists():
        return []
    samples = []
    for row in json.loads(index.read_text(encoding="utf-8")):
        samples.append(
            Sample(
                id=row["id"],
                title=row["title"],
                description=row["description"],
                file_name=row["file_name"],
                pdf=(directory / "pdfs" / row["file_name"]).read_bytes(),
                extraction=InvoiceExtraction.model_validate(row["extraction"]),
                usage=Usage.model_validate(row["usage"]) if row.get("usage") else None,
            )
        )
    return samples


@lru_cache()
def get_samples() -> tuple[Sample, ...]:
    return tuple(load_samples())


class DemoExtractor:
    def __init__(self, samples: tuple[Sample, ...] | None = None) -> None:
        self._by_hash = {hashlib.sha256(s.pdf).hexdigest(): s for s in (samples if samples is not None else get_samples())}

    async def extract(self, pdf: bytes) -> tuple[InvoiceExtraction, Usage | None]:
        sample = self._by_hash.get(hashlib.sha256(pdf).hexdigest())
        if sample is None:
            raise NotASampleError(
                "Demo mode only accepts the bundled sample documents. "
                "Run the API with EXTRACTOR=gemini and an API key to process other PDFs."
            )
        return sample.extraction, sample.usage
