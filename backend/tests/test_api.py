import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import settings
from app.core.limits import ConcurrencyGate, SlidingWindowLimiter
from app.main import app
from evals.runner import OracleExtractor
from evals.synth.dataset import load_split

URL = "/api/v1/extractions"
SAMPLES = load_split("dev")
CLEAN = next(s for s in SAMPLES if s.injected_error is None and s.difficulty == "easy")
BROKEN = next(s for s in SAMPLES if s.injected_error is not None)
TWO_PAGES = next(s for s in SAMPLES if s.doc_id == "dev-hard-00")  # rendered on two pages


def upload(sample_or_bytes, name="invoice.pdf", content_type="application/pdf"):
    data = sample_or_bytes if isinstance(sample_or_bytes, bytes) else sample_or_bytes.pdf_bytes()
    return {"file": (name, data, content_type)}


class ExplodingExtractor:
    async def extract(self, pdf):
        raise RuntimeError("upstream exploded with secret details")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(deps, "_extraction_limiter", SlidingWindowLimiter(3, 600))
    monkeypatch.setattr(deps, "_extraction_gate", ConcurrencyGate(2))
    app.dependency_overrides[deps.get_extractor] = lambda: OracleExtractor(SAMPLES)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_clean_invoice_is_extracted_without_review(client):
    response = client.post(URL, files=upload(CLEAN))

    assert response.status_code == 200
    body = response.json()
    assert body["extraction"]["invoice_number"] == CLEAN.truth.invoice_number
    assert body["issues"] == [] and body["needs_review"] is False


def test_inconsistent_invoice_is_flagged_for_review(client):
    body = client.post(URL, files=upload(BROKEN)).json()

    assert body["needs_review"] is True
    assert any(issue["severity"] == "error" for issue in body["issues"])


def test_non_pdf_is_rejected_by_content_not_by_declared_type(client):
    assert client.post(URL, files=upload(b"just text", "x.pdf", "application/pdf")).status_code == 415
    assert client.post(URL, files=upload(b"\x89PNG\r\n", "x.png", "image/png")).status_code == 415


def test_pdf_header_without_a_readable_document_is_422(client):
    assert client.post(URL, files=upload(b"%PDF-1.7 garbage that is not a pdf")).status_code == 422


def test_oversized_upload_is_413(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 0)
    assert client.post(URL, files=upload(CLEAN)).status_code == 413


def test_too_many_pages_is_422(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_PDF_PAGES", 1)
    response = client.post(URL, files=upload(TWO_PAGES))

    assert response.status_code == 422 and "2 pages" in response.json()["detail"]


def test_rate_limit_returns_429_with_retry_after(client):
    for _ in range(3):
        assert client.post(URL, files=upload(CLEAN)).status_code == 200
    blocked = client.post(URL, files=upload(CLEAN))

    assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) >= 1


def test_busy_service_returns_503(client):
    deps._extraction_gate.try_acquire()
    deps._extraction_gate.try_acquire()

    assert client.post(URL, files=upload(CLEAN)).status_code == 503


def test_extractor_failure_hides_details_and_frees_the_slot(client):
    app.dependency_overrides[deps.get_extractor] = lambda: ExplodingExtractor()
    response = client.post(URL, files=upload(CLEAN))

    assert response.status_code == 500
    assert "secret" not in response.text
    assert deps._extraction_gate.active == 0


def test_missing_api_key_gives_503_when_gemini_is_requested_explicitly(monkeypatch):
    monkeypatch.setattr(settings, "EXTRACTOR", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    deps._build_extractor.cache_clear()
    monkeypatch.setattr(deps, "_extraction_limiter", SlidingWindowLimiter(5, 600))

    response = TestClient(app).post(URL, files=upload(CLEAN))

    assert response.status_code == 503 and "not configured" in response.json()["detail"]


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"
