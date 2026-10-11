from pydantic import BaseModel, Field


class Usage(BaseModel):
    """Cost and latency of one model call, for observability and for the numbers in the README."""

    model: str
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    total_tokens: int
    latency_s: float
    estimated_cost_usd: float | None = Field(
        default=None, description="None unless PRICE_INPUT_PER_MTOK / PRICE_OUTPUT_PER_MTOK are configured"
    )
