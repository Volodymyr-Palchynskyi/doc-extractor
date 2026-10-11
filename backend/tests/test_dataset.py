"""The synthetic datasets are the foundation of every number this project reports, so they get their own checks."""
import json
from collections import Counter

import pypdfium2 as pdfium
import pytest

from app.services.validation import validate_invoice
from evals.synth.dataset import DATASET_DIR, SPLITS, build_split, iter_synthetic, load_split
from evals.synth.render import render_pdf


@pytest.mark.parametrize("split", SPLITS)
def test_split_has_the_planned_composition(split):
    samples = load_split(split)

    assert Counter(s.difficulty for s in samples) == Counter(SPLITS[split])
    assert len({s.doc_id for s in samples}) == len(samples)
    assert all(s.pdf_path.exists() for s in samples)


@pytest.mark.parametrize("split", SPLITS)
def test_validator_agrees_with_the_errors_the_generator_injected(split):
    """Ground truth is exact by construction and the validator is independent code: they must agree."""
    for sample in load_split(split):
        has_error = any(i.severity == "error" for i in validate_invoice(sample.truth))
        assert has_error == (sample.injected_error is not None), sample.doc_id


@pytest.mark.parametrize("split", SPLITS)
def test_committed_dataset_is_what_the_generator_produces(split, tmp_path):
    build_split(split, tmp_path)

    committed = (DATASET_DIR / split / "truth.jsonl").read_text(encoding="utf-8")
    rebuilt = (tmp_path / split / "truth.jsonl").read_text(encoding="utf-8")
    assert [json.loads(line) for line in rebuilt.splitlines()] == [json.loads(line) for line in committed.splitlines()]
    for sample in load_split(split):
        assert len(pdfium.PdfDocument(tmp_path / split / f"{sample.doc_id}.pdf")) == len(pdfium.PdfDocument(sample.pdf_path))


def test_rendering_is_byte_deterministic():
    inv = next(iter_synthetic("dev"))
    assert render_pdf(inv) == render_pdf(inv)


def test_dev_and_test_splits_do_not_share_documents():
    dev = {json.dumps(s.truth.model_dump(mode="json"), sort_keys=True) for s in load_split("dev")}
    test = {json.dumps(s.truth.model_dump(mode="json"), sort_keys=True) for s in load_split("test")}
    assert not dev & test


def test_hard_documents_cover_the_difficulties_they_claim():
    hard = [s for s in load_split("dev") if s.difficulty == "hard"]
    pages = [len(pdfium.PdfDocument(s.pdf_path)) for s in hard]

    assert max(pages) >= 2, "no multi-page document among the hard ones"
    assert any(s.injected_error for s in hard), "no printed arithmetic error among the hard ones"
    assert {s.locale for s in hard} - {"en_US", "en_GB"}, "hard documents never use a non-English number format"
