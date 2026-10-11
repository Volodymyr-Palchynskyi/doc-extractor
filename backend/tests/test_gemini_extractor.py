import json
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.schemas.invoice import InvoiceExtraction
from app.services.extraction_service import SYSTEM_INSTRUCTION, GeminiExtractor, extract_and_validate
from evals.synth.dataset import load_split

SAMPLE = next(s for s in load_split("dev") if s.injected_error is None and s.difficulty == "easy")
USAGE = SimpleNamespace(prompt_token_count=1000, candidates_token_count=400, thoughts_token_count=100, total_token_count=1500)


class FakeModels:
    def __init__(self, text: str | None, usage=USAGE) -> None:
        self.text, self.usage, self.calls = text, usage, []

    async def generate_content(self, model, contents, config):
        self.calls.append(SimpleNamespace(model=model, contents=contents, config=config))
        return SimpleNamespace(text=self.text, usage_metadata=self.usage)


def make_extractor(monkeypatch, models: FakeModels, **settings_overrides) -> GeminiExtractor:
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    for key, value in settings_overrides.items():
        monkeypatch.setattr(settings, key, value)
    extractor = GeminiExtractor()
    extractor._client = SimpleNamespace(aio=SimpleNamespace(models=models))
    return extractor


def truth_json() -> str:
    return json.dumps(SAMPLE.truth.model_dump(mode="json"))


async def test_sends_the_pdf_itself_with_a_strict_schema_and_zero_temperature(monkeypatch):
    models = FakeModels(truth_json())
    extractor = make_extractor(monkeypatch, models)

    invoice, _ = await extractor.extract(SAMPLE.pdf_bytes())

    call = models.calls[0]
    part = call.contents[0]
    assert part.inline_data.mime_type == "application/pdf" and part.inline_data.data == SAMPLE.pdf_bytes()
    assert call.config.response_schema is InvoiceExtraction
    assert call.config.temperature == 0.0
    assert call.config.system_instruction == SYSTEM_INSTRUCTION
    assert invoice == SAMPLE.truth


async def test_usage_tokens_and_optional_cost(monkeypatch):
    priced = make_extractor(monkeypatch, FakeModels(truth_json()), PRICE_INPUT_PER_MTOK=0.5, PRICE_OUTPUT_PER_MTOK=3.0)
    _, usage = await priced.extract(SAMPLE.pdf_bytes())

    assert (usage.input_tokens, usage.output_tokens, usage.thinking_tokens, usage.total_tokens) == (1000, 400, 100, 1500)
    assert usage.estimated_cost_usd == pytest.approx((1000 * 0.5 + 500 * 3.0) / 1_000_000)

    unpriced = make_extractor(monkeypatch, FakeModels(truth_json()), PRICE_INPUT_PER_MTOK=0.0, PRICE_OUTPUT_PER_MTOK=0.0)
    assert (await unpriced.extract(SAMPLE.pdf_bytes()))[1].estimated_cost_usd is None


async def test_empty_model_response_is_an_error(monkeypatch):
    extractor = make_extractor(monkeypatch, FakeModels(None))
    with pytest.raises(RuntimeError, match="empty"):
        await extractor.extract(SAMPLE.pdf_bytes())


async def test_extract_and_validate_flags_inconsistent_values(monkeypatch):
    broken = SAMPLE.truth.model_copy(update={"total": SAMPLE.truth.total + 100})
    extractor = make_extractor(monkeypatch, FakeModels(json.dumps(broken.model_dump(mode="json"))))

    result = await extract_and_validate(extractor, SAMPLE.pdf_bytes())

    assert result.needs_review and [i.code for i in result.issues] == ["total_mismatch"]
    assert result.usage.total_tokens == 1500


def test_missing_api_key_is_a_configuration_error(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiExtractor()


def test_instruction_tells_the_model_not_to_fix_numbers():
    assert "AS PRINTED" in SYSTEM_INSTRUCTION and "never correct" in SYSTEM_INSTRUCTION
