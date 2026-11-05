from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.negotiation.demo import (
    DemoNegotiationRequest,
    DemoNegotiationResponse,
    DemoNegotiationService,
    DemoProfile,
    demo_intent_extractor,
)
from app.modules.negotiation.llm import LLMUnavailableError
from app.modules.negotiation.router import get_offer_service
from app.modules.negotiation.service import OfferService

router = APIRouter(prefix="/demo", tags=["demo negotiation"])


def get_demo_service(offer_service: OfferService = Depends(get_offer_service)) -> DemoNegotiationService:
    extractor, provider = demo_intent_extractor()
    return DemoNegotiationService(offer_service, extractor, provider)


@router.get("/profiles", response_model=list[DemoProfile])
def list_demo_profiles(service: DemoNegotiationService = Depends(get_demo_service)) -> list[DemoProfile]:
    return service.profiles()


@router.post("/negotiations/run", response_model=DemoNegotiationResponse)
def run_demo_negotiation(
    request: DemoNegotiationRequest,
    service: DemoNegotiationService = Depends(get_demo_service),
) -> DemoNegotiationResponse:
    try:
        return service.run(request)
    except LLMUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "LLM_UNAVAILABLE", "message": str(error)},
        ) from error
