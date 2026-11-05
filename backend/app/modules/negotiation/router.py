from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.negotiation.repository import InMemoryOfferRepository, OfferNotFoundError
from app.modules.negotiation.schemas import (
    AcceptanceRequest,
    CounterOfferRequest,
    CreateOfferRequest,
    OfferResponse,
)
from app.modules.negotiation.service import (
    AuthoritativeQuoteRequiredError,
    OfferConflictError,
    OfferService,
)

router = APIRouter(prefix="/offers", tags=["offers"])
_repository = InMemoryOfferRepository()
_service = OfferService(_repository)


def get_offer_service() -> OfferService:
    return _service


OfferServiceDependency = Annotated[OfferService, Depends(get_offer_service)]


@router.post("", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
def create_offer(request: CreateOfferRequest, service: OfferServiceDependency) -> OfferResponse:
    return service.create(request)


@router.get("", response_model=list[OfferResponse])
def list_offers(
    request_id: Annotated[UUID, Query(alias="request_id")], service: OfferServiceDependency
) -> list[OfferResponse]:
    return service.list_by_request(request_id)


@router.get("/{offer_id}", response_model=OfferResponse)
def get_offer(offer_id: UUID, service: OfferServiceDependency) -> OfferResponse:
    try:
        return service.get(offer_id)
    except OfferNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="offer not found") from error


@router.post("/{offer_id}/counter", response_model=OfferResponse)
def counter_offer(
    offer_id: UUID, request: CounterOfferRequest, service: OfferServiceDependency
) -> OfferResponse:
    try:
        return service.counter(offer_id, request)
    except OfferNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="offer not found") from error
    except OfferConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post("/{offer_id}/accept", response_model=OfferResponse)
def accept_offer(
    offer_id: UUID, request: AcceptanceRequest, service: OfferServiceDependency
) -> OfferResponse:
    try:
        return service.accept(offer_id, request)
    except OfferNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="offer not found") from error
    except AuthoritativeQuoteRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "AUTHORITATIVE_QUOTE_REQUIRED", "message": str(error)},
        ) from error
    except OfferConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
