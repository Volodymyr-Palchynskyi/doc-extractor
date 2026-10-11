"""
Record the demo-mode samples: run the REAL model on a few dataset documents and store its output.

    uv run python -m evals.record_demo      # needs GEMINI_API_KEY, makes one model call per sample

The result goes to app/demo/ (PDFs + samples.json). Re-run it if the schema or the prompt changes, so the demo
keeps showing what the current system really does, mistakes included.
"""
import asyncio
import json
import shutil

from app.schemas.usage import Usage
from app.services.demo_extractor import DEMO_DIR
from app.services.extraction_service import GeminiExtractor
from evals.synth.dataset import load_split

SAMPLES = [
    ("english-clean", "dev-easy-00", "English invoice, clean",
     "A straightforward US invoice with five lines. A good first upload: everything adds up."),
    ("french-two-pages", "dev-hard-00", "French invoice, two pages",
     "29 lines over two pages, European number format (1 659,30 €), a purchase order number and a "
     "'replaces invoice' note next to the real invoice number."),
    ("german-wrong-total", "dev-hard-03", "German invoice with a wrong total",
     "The total printed on the page does not match its own lines. The model copies it faithfully and "
     "the validator flags it, which is the point of the project."),
]


async def main() -> None:
    by_id = {s.doc_id: s for s in load_split("dev")}
    extractor = GeminiExtractor()
    (DEMO_DIR / "pdfs").mkdir(parents=True, exist_ok=True)

    rows = []
    for sample_id, doc_id, title, description in SAMPLES:
        sample = by_id[doc_id]
        file_name = f"{sample_id}.pdf"
        shutil.copy(sample.pdf_path, DEMO_DIR / "pdfs" / file_name)
        extraction, usage = await extractor.extract(sample.pdf_bytes())
        print(f"{sample_id}: {len(extraction.line_items)} lines, total {extraction.total}")
        rows.append({
            "id": sample_id, "title": title, "description": description, "file_name": file_name,
            "extraction": extraction.model_dump(mode="json"),
            "usage": usage.model_dump(mode="json") if isinstance(usage, Usage) else None,
        })
    (DEMO_DIR / "samples.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} samples to {DEMO_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
