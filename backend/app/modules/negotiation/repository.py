from uuid import UUID

from app.modules.negotiation.schemas import OfferRecord


class OfferNotFoundError(LookupError):
    pass


class InMemoryOfferRepository:
    """Temporary composition-root repository until the shared DB is introduced."""

    def __init__(self) -> None:
        self._offers: dict[UUID, OfferRecord] = {}

    def save(self, offer: OfferRecord) -> OfferRecord:
        self._offers[offer.id] = offer
        return offer

    def get(self, offer_id: UUID) -> OfferRecord:
        try:
            return self._offers[offer_id]
        except KeyError as error:
            raise OfferNotFoundError(str(offer_id)) from error

    def list_by_request(self, procurement_request_id: UUID) -> list[OfferRecord]:
        return [
            offer
            for offer in self._offers.values()
            if offer.procurement_request_id == procurement_request_id
        ]
