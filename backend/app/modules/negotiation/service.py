from datetime import UTC, datetime
from uuid import UUID

from app.modules.negotiation.repository import InMemoryOfferRepository
from app.modules.negotiation.schemas import (
    AcceptanceRequest,
    CounterOfferRequest,
    CreateOfferRequest,
    OfferRecord,
    OfferResponse,
    OfferState,
    OfferValidation,
    ValidationStatus,
)


class OfferConflictError(ValueError):
    pass


class AuthoritativeQuoteRequiredError(ValueError):
    pass


class OfferService:
    def __init__(self, repository: InMemoryOfferRepository) -> None:
        self._repository = repository

    def create(self, request: CreateOfferRequest) -> OfferResponse:
        validation = self._validate_ceiling(
            request.terms.estimated_landed_unit_cost_minor,
            request.price_ceiling_per_unit_minor,
        )
        record = OfferRecord(
            procurement_request_id=request.procurement_request_id,
            buyer_id=request.buyer_id,
            seller_id=request.seller_id,
            actor_id=request.actor_id,
            price_ceiling_per_unit_minor=request.price_ceiling_per_unit_minor,
            terms=request.terms,
            validation=validation,
        )
        return self._repository.save(record).response()

    def get(self, offer_id: UUID) -> OfferResponse:
        return self._repository.get(offer_id).response()

    def list_by_request(self, procurement_request_id: UUID) -> list[OfferResponse]:
        return [offer.response() for offer in self._repository.list_by_request(procurement_request_id)]

    def counter(self, offer_id: UUID, request: CounterOfferRequest) -> OfferResponse:
        offer = self._repository.get(offer_id)
        if offer.state not in {OfferState.SUBMITTED, OfferState.COUNTERED}:
            raise OfferConflictError("only submitted or countered offers can be countered")

        offer.terms = request.terms
        offer.actor_id = request.actor_id
        offer.version += 1
        offer.state = OfferState.COUNTERED
        offer.validation = self._validate_ceiling(
            request.terms.estimated_landed_unit_cost_minor,
            offer.price_ceiling_per_unit_minor,
        )
        offer.updated_at = datetime.now(UTC)
        return self._repository.save(offer).response()

    def accept(self, offer_id: UUID, request: AcceptanceRequest) -> OfferResponse:
        offer = self._repository.get(offer_id)
        if offer.state not in {OfferState.SUBMITTED, OfferState.COUNTERED}:
            raise OfferConflictError("only submitted or countered offers can be accepted")
        if request.actor_id != offer.buyer_id:
            raise OfferConflictError("only the buyer may accept an offer")
        if offer.validation.status is ValidationStatus.FAILED:
            raise OfferConflictError("an offer above the price ceiling cannot be accepted")

        # Pooling/optimization owns the final allocation quote. Failing closed
        # here prevents an estimate or agent result from becoming authoritative.
        raise AuthoritativeQuoteRequiredError(
            "authoritative allocation quote is required before acceptance"
        )

    @staticmethod
    def _validate_ceiling(landed_unit_cost_minor: int, ceiling_minor: int) -> OfferValidation:
        if landed_unit_cost_minor > ceiling_minor:
            return OfferValidation(
                status=ValidationStatus.FAILED,
                reason="estimated landed unit cost exceeds the retailer price ceiling",
            )
        return OfferValidation(
            status=ValidationStatus.PENDING_AUTHORITATIVE_QUOTE,
            reason="estimate is within ceiling; final allocation quote is still required",
        )
