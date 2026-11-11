import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from app.modules.negotiation.procurement_schemas import ProcurementIntent, ProcurementParseRequest

_QUANTITY = re.compile(
    r"\b(?P<quantity>\d+(?:\.\d+)?)\s*(?P<unit>kg|g|l|ml|units?|packs?|boxes?)\b",
    re.IGNORECASE,
)
_PRICE_CEILING = re.compile(
    r"(?:landed\s+)?(?:price|cost)\s*(?:below|under|less\s+than|<=)\s*"
    r"(?:₹|\$|usd|eur|gbp|inr|rs\.?)?\s*(?P<amount>\d+(?:\.\d+)?)\s*(?:/\s*(?P<unit>kg|g|l|ml|unit|pack|box))?",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(r"\b(?P<date>\d{4}-\d{2}-\d{2})\b")
_BY_DATE = re.compile(r"\bby\s+(?P<date>[^,;.]+)", re.IGNORECASE)


class DeterministicProcurementParser:
    """A transparent fallback parser used until a structured-output LLM is wired in."""

    def parse(self, request: ProcurementParseRequest) -> ProcurementIntent:
        message = " ".join(request.message.split())
        currency = request.currency.upper()
        quantity_match = _QUANTITY.search(message)
        price_match = _PRICE_CEILING.search(message)
        date_match = _ISO_DATE.search(message)
        by_date_match = _BY_DATE.search(message)

        quantity = None
        quantity_unit = None
        if quantity_match:
            quantity = Decimal(quantity_match.group("quantity"))
            quantity_unit = quantity_match.group("unit").lower().rstrip("s")

        ceiling_minor = self._to_minor_units(price_match.group("amount")) if price_match else None
        delivery_date = self._parse_date(date_match.group("date")) if date_match else None
        delivery_date_text = by_date_match.group("date").strip() if by_date_match else None
        product = self._extract_product(message, quantity_match, by_date_match, price_match)
        lower_message = message.lower()
        substitution_consent = any(
            phrase in lower_message
            for phrase in ("substitute allowed", "substitutes allowed", "equivalent brands allowed")
        )
        protected = ("rice variety",) if "variety unchanged" in lower_message else ()

        questions: list[str] = []
        if not product:
            questions.append("What product and required specification do you need?")
        if quantity is None:
            questions.append("What quantity and unit do you need?")
        if delivery_date is None:
            questions.append("What is the delivery date? Please provide it as YYYY-MM-DD.")
        if ceiling_minor is None:
            questions.append("What is the hard landed-price ceiling per unit?")

        return ProcurementIntent(
            source_message=message,
            product_description=product,
            quantity=quantity,
            quantity_unit=quantity_unit,
            delivery_date=delivery_date,
            delivery_date_text=delivery_date_text,
            price_ceiling_per_unit_minor=ceiling_minor,
            currency=currency,
            substitution_consent=substitution_consent,
            protected_attributes=protected,
            clarification_questions=tuple(questions),
        )

    @staticmethod
    def _to_minor_units(amount: str) -> int:
        try:
            return int((Decimal(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        except InvalidOperation as error:
            raise ValueError("price amount must be numeric") from error

    @staticmethod
    def _parse_date(value: str) -> date | None:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _extract_product(
        message: str,
        quantity_match: re.Match[str] | None,
        by_date_match: re.Match[str] | None,
        price_match: re.Match[str] | None,
    ) -> str | None:
        if not quantity_match:
            return None
        start = quantity_match.end()
        end_candidates = [match.start() for match in (by_date_match, price_match) if match]
        end = min(end_candidates) if end_candidates else len(message)
        product = message[start:end].strip(" ,;.-")
        return product or None
