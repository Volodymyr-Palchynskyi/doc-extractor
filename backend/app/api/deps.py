import logging
from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings
from app.core.limits import ConcurrencyGate, SlidingWindowLimiter
from app.services.extraction_service import GeminiExtractor, PdfExtractor

logger = logging.getLogger(__name__)


@lru_cache()
def _build_extractor() -> PdfExtractor:
    return GeminiExtractor()


def get_extractor() -> PdfExtractor:
    try:
        return _build_extractor()
    except ValueError as exc:  # missing configuration, e.g. no API key
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"The service is not configured: {exc}") from exc


# ------------------------------------------------------------------ abuse protection
_extraction_limiter = SlidingWindowLimiter(settings.RATE_LIMIT_EXTRACTIONS, settings.RATE_LIMIT_WINDOW_S)
_extraction_gate = ConcurrencyGate(settings.MAX_CONCURRENT_EXTRACTIONS)


def _client_key(request: Request) -> str:
    # Behind a reverse proxy run uvicorn with --proxy-headers so this is the real client IP.
    return request.client.host if request.client else "unknown"


def limit_extractions(request: Request) -> None:
    retry_after = _extraction_limiter.check(_client_key(request))
    if retry_after is not None:
        seconds = max(1, int(retry_after) + 1)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Rate limit reached. Try again in {seconds} s.",
            headers={"Retry-After": str(seconds)},
        )


def acquire_extraction_slot(_: None = Depends(limit_extractions)) -> Iterator[None]:
    """Non-blocking cap on simultaneous model calls: a busy service answers 503 at once instead of queueing."""
    slot_id = _extraction_gate.try_acquire()
    if slot_id is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The service is busy extracting other documents. Please retry in a moment.",
            headers={"Retry-After": "15"},
        )
    try:
        yield
    finally:
        _extraction_gate.release(slot_id)
