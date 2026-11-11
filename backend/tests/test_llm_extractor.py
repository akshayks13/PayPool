from datetime import date
from decimal import Decimal

import pytest

from app.modules.negotiation.llm import GeminiProcurementExtractor, LLMExtraction
from app.modules.negotiation.procurement_schemas import ProcurementParseRequest


def test_llm_extraction_is_normalized_and_missing_fields_are_enforced() -> None:
    extracted = LLMExtraction(
        product_description="Sona Masoori rice",
        quantity=Decimal("30"),
        quantity_unit="KG",
        delivery_date=date(2026, 11, 13),
        delivery_date_text="2026-11-13",
        price_ceiling_per_unit_minor=5_200,
        substitution_consent=True,
        protected_attributes=("rice variety",),
    )

    intent = GeminiProcurementExtractor._to_intent(
        ProcurementParseRequest(message="untrusted message", currency="inr"), extracted
    )

    assert intent.currency == "INR"
    assert intent.quantity_unit == "kg"
    assert intent.clarification_questions == ()
    assert intent.confirmation_required is True


def test_llm_extraction_cannot_suppress_required_clarification() -> None:
    intent = GeminiProcurementExtractor._to_intent(
        ProcurementParseRequest(message="I need supplies"), LLMExtraction()
    )

    assert len(intent.clarification_questions) == 4


@pytest.mark.parametrize(
    "model_unit,expected",
    [
        (" kilograms ", "kg"),
        ("Litres", "l"),
        ("boxes", "box"),
        ("grams", "g"),
        ("carton", "carton"),
    ],
)
def test_unit_spelling_preserves_quantity_and_price_basis(model_unit, expected):
    intent = GeminiProcurementExtractor._to_intent(
        ProcurementParseRequest(message="buyer requirements", currency="USD"),
        LLMExtraction(
            product_description="Rice",
            quantity=Decimal("30"),
            quantity_unit=model_unit,
            price_ceiling_per_unit_minor=170,
            delivery_date=date(2026, 11, 13),
        ),
    )
    assert intent.quantity_unit == expected
    assert intent.quantity == Decimal("30")
    assert intent.price_ceiling_per_unit_minor == 170
    assert intent.clarification_questions == ()


def test_blank_product_and_unit_still_require_clarification():
    intent = GeminiProcurementExtractor._to_intent(
        ProcurementParseRequest(message="buyer requirements"),
        LLMExtraction(
            product_description=" ", quantity=Decimal("30"), quantity_unit=" "
        ),
    )
    assert intent.product_description is None
    assert intent.quantity_unit is None
    assert len(intent.clarification_questions) == 4
