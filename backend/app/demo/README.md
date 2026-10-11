# Demo samples

`samples.json` and `pdfs/` are the data behind `EXTRACTOR=demo`.

The extractions in `samples.json` are **real output of the model** on exactly these PDFs (the PDFs are
copies of documents from `evals/dataset/dev`), recorded with:

```bash
uv run python -m evals.record_demo      # needs GEMINI_API_KEY, one model call per sample
```

They are not hand-written, so the demo shows what the system really does, mistakes included. Re-record after
changing the schema or the prompt.
