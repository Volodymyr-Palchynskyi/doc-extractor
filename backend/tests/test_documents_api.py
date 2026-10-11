import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import settings
from app.core.limits import ConcurrencyGate, SlidingWindowLimiter
from app.main import app
from app.services.demo_extractor import DemoExtractor, get_samples
from app.services.document_store import DocumentStore
from evals.runner import OracleExtractor
from evals.synth.dataset import load_split

API = "/api/v1"
SAMPLES = load_split("dev")
ONE_PAGE = next(s for s in SAMPLES if s.difficulty == "easy")
TWO_PAGES = next(s for s in SAMPLES if s.doc_id == "dev-hard-00")
PNG = b"\x89PNG\r\n\x1a\n"


class Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def client(monkeypatch, clock):
    monkeypatch.setattr(deps, "_extraction_limiter", SlidingWindowLimiter(50, 600))
    monkeypatch.setattr(deps, "_extraction_gate", ConcurrencyGate(5))
    monkeypatch.setattr(deps, "_page_limiter", SlidingWindowLimiter(100, 600))
    monkeypatch.setattr(deps, "_validation_limiter", SlidingWindowLimiter(100, 600))
    store = DocumentStore(ttl_s=60, max_docs=10, max_bytes=50 * 1024 * 1024, clock=clock)
    app.dependency_overrides[deps.get_document_store] = lambda: store
    app.dependency_overrides[deps.get_extractor] = lambda: OracleExtractor(SAMPLES)
    yield TestClient(app)
    app.dependency_overrides.clear()


def upload(client, sample):
    return client.post(f"{API}/extractions", files={"file": ("x.pdf", sample.pdf_bytes(), "application/pdf")})


# ------------------------------------------------------------------ page images

def test_upload_returns_a_document_handle_and_page_count(client):
    body = upload(client, TWO_PAGES).json()

    assert body["pages"] == 2 and len(body["document_id"]) >= 20


def test_every_page_renders_as_png(client):
    doc_id = upload(client, TWO_PAGES).json()["document_id"]

    for page in (1, 2):
        response = client.get(f"{API}/documents/{doc_id}/pages/{page}.png")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(PNG)
        assert "private" in response.headers["cache-control"]


def test_missing_page_unknown_document_and_page_zero(client):
    doc_id = upload(client, ONE_PAGE).json()["document_id"]

    assert client.get(f"{API}/documents/{doc_id}/pages/2.png").status_code == 404
    assert client.get(f"{API}/documents/does-not-exist/pages/1.png").status_code == 404
    assert client.get(f"{API}/documents/{doc_id}/pages/0.png").status_code == 422


def test_document_disappears_after_the_ttl(client, clock):
    doc_id = upload(client, ONE_PAGE).json()["document_id"]
    assert client.get(f"{API}/documents/{doc_id}/pages/1.png").status_code == 200

    clock.now = 61
    assert client.get(f"{API}/documents/{doc_id}/pages/1.png").status_code == 404


def test_delete_removes_the_document_and_is_idempotent(client):
    doc_id = upload(client, ONE_PAGE).json()["document_id"]

    assert client.delete(f"{API}/documents/{doc_id}").status_code == 204
    assert client.get(f"{API}/documents/{doc_id}/pages/1.png").status_code == 404
    assert client.delete(f"{API}/documents/{doc_id}").status_code == 204


def test_failed_extraction_stores_nothing(client):
    class Boom:
        async def extract(self, pdf):
            raise RuntimeError("no")

    app.dependency_overrides[deps.get_extractor] = lambda: Boom()
    assert upload(client, ONE_PAGE).status_code == 500
    assert len(app.dependency_overrides[deps.get_document_store]()) == 0


def test_page_requests_are_rate_limited(client, monkeypatch):
    monkeypatch.setattr(deps, "_page_limiter", SlidingWindowLimiter(2, 600))
    doc_id = upload(client, ONE_PAGE).json()["document_id"]

    statuses = [client.get(f"{API}/documents/{doc_id}/pages/1.png").status_code for _ in range(3)]
    assert statuses == [200, 200, 429]


# ------------------------------------------------------------------ re-validation

def edited(sample, **changes) -> dict:
    return {**sample.truth.model_dump(mode="json"), **changes}


def test_consistent_values_have_no_issues(client):
    result = client.post(f"{API}/validations", json=edited(ONE_PAGE)).json()

    assert result == {"issues": [], "needs_review": False}


def test_an_edited_total_is_caught_without_any_model_call(client):
    app.dependency_overrides[deps.get_extractor] = lambda: pytest.fail("validation must not call the model")
    result = client.post(f"{API}/validations", json=edited(ONE_PAGE, total=1.0)).json()

    assert result["needs_review"] is True
    assert [i["code"] for i in result["issues"]] == ["total_mismatch"]


def test_a_fixed_value_clears_the_issue(client):
    broken = next(s for s in SAMPLES if s.injected_error == "total_off")
    assert client.post(f"{API}/validations", json=edited(broken)).json()["needs_review"] is True

    fixed_total = round(broken.truth.subtotal - broken.truth.discount_total + broken.truth.tax_total, 2)
    assert client.post(f"{API}/validations", json=edited(broken, total=fixed_total)).json()["needs_review"] is False


def test_too_many_line_items_are_rejected(client):
    item = ONE_PAGE.truth.line_items[0].model_dump(mode="json")
    response = client.post(f"{API}/validations", json=edited(ONE_PAGE, line_items=[item] * 501))

    assert response.status_code == 422


def test_malformed_payload_is_422(client):
    assert client.post(f"{API}/validations", json={"total": "abc"}).status_code == 422


# ------------------------------------------------------------------ samples, info, demo mode

def test_info_reports_mode_and_limits(client):
    body = client.get(f"{API}/info").json()

    assert body["mode"] in ("gemini", "demo")
    assert body["max_upload_mb"] == settings.MAX_UPLOAD_MB and body["document_ttl_s"] == settings.DOC_TTL_S


def test_bundled_samples_are_listed_and_downloadable(client):
    samples = client.get(f"{API}/samples").json()

    assert len(samples) >= 3 and all(s["title"] and s["description"] for s in samples)
    pdf = client.get(f"{API}/samples/{samples[0]['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    assert client.get(f"{API}/samples/nope/pdf").status_code == 404


def test_demo_mode_replays_the_recorded_output_for_a_sample(client):
    app.dependency_overrides[deps.get_extractor] = lambda: DemoExtractor()
    sample = next(s for s in get_samples() if s.id == "german-wrong-total")

    response = client.post(f"{API}/extractions", files={"file": ("x.pdf", sample.pdf, "application/pdf")})

    assert response.status_code == 200
    body = response.json()
    assert body["extraction"]["total"] == sample.extraction.total
    assert body["needs_review"] is True and body["issues"][0]["code"] == "total_mismatch"


def test_demo_mode_refuses_other_documents_with_a_clear_message(client):
    app.dependency_overrides[deps.get_extractor] = lambda: DemoExtractor()
    not_a_sample = next(s for s in SAMPLES if s.doc_id == "dev-easy-01")  # ONE_PAGE itself IS a bundled sample

    response = upload(client, not_a_sample)

    assert response.status_code == 422 and "Demo mode" in response.json()["detail"]


@pytest.mark.parametrize(
    "extractor, key, expected",
    [("auto", "", "demo"), ("auto", "some-key", "gemini"), ("gemini", "", "gemini"), ("demo", "some-key", "demo")],
)
def test_effective_mode_resolution(monkeypatch, extractor, key, expected):
    monkeypatch.setattr(settings, "EXTRACTOR", extractor)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", key)

    assert settings.extractor_mode == expected


def test_info_reports_the_effective_mode(client, monkeypatch):
    monkeypatch.setattr(settings, "EXTRACTOR", "auto")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    assert client.get(f"{API}/info").json()["mode"] == "demo"
