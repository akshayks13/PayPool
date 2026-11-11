import os

from fastapi import APIRouter, HTTPException, status

from app.modules.negotiation.llm import GeminiProcurementExtractor, LLMUnavailableError
from app.modules.negotiation.procurement_parser import DeterministicProcurementParser
from app.modules.negotiation.procurement_schemas import ProcurementIntent, ProcurementParseRequest

router = APIRouter(prefix="/procurement", tags=["procurement"])

def get_procurement_parser() -> DeterministicProcurementParser | GeminiProcurementExtractor:
    """Gemini is the normal runtime path; deterministic mode is local/test-only."""
    offline_demo = os.getenv("PAYPOOL_DEMO_MODE", "true").lower() == "true" and not os.getenv("GEMINI_API_KEY")
    provider = os.getenv("PAYPOOL_LLM_PROVIDER", "deterministic" if offline_demo else "gemini").lower()
    if provider == "deterministic":
        return DeterministicProcurementParser()
    if provider == "gemini":
        return GeminiProcurementExtractor.from_environment()
    raise LLMUnavailableError(f"unsupported LLM provider: {provider}")


@router.post("/parse", response_model=ProcurementIntent)
def parse_procurement_request(request: ProcurementParseRequest) -> ProcurementIntent:
    """Extract an intent for retailer confirmation; never creates an order or offer."""
    try:
        return get_procurement_parser().parse(request)
    except LLMUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "LLM_UNAVAILABLE", "message": str(error)},
        ) from error
