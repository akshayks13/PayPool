from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Input):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class Tier(Input):
    minimum_quantity: int = Field(gt=0, le=1000000)
    unit_price_minor: int = Field(gt=0, le=100000000)


class Product(Input):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=2000)
    category: str = Field(default="General", max_length=100)
    pack: str = Field(default="", max_length=100)
    image_url: str = Field(default="", max_length=1000)
    product_url: str = Field(default="", max_length=1000)
    active: bool = True
    negotiation_floor_minor: int | None = Field(default=None, gt=0)
    unit: str = Field(default="kg", min_length=1, max_length=20)
    currency: Literal["USD", "EUR", "GBP", "INR"] = "USD"
    stock: int = Field(ge=0, le=1000000)
    weight_grams: int = Field(default=1000, gt=0, le=1000000)
    volume_cm3: int = Field(default=1500, gt=0, le=10000000)
    attributes: dict[str, str] = Field(default_factory=dict)
    tiers: list[Tier] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def ordered_tiers(self):
        if len({t.minimum_quantity for t in self.tiers}) != len(self.tiers):
            raise ValueError("quantity thresholds must be unique")
        values = sorted(self.tiers, key=lambda t: t.minimum_quantity)
        if values[0].minimum_quantity != 1:
            raise ValueError("include a base price at quantity 1")
        if any(
            b.unit_price_minor > a.unit_price_minor for a, b in zip(values, values[1:])
        ):
            raise ValueError("volume prices must not increase")
        self.tiers = values
        if (
            self.negotiation_floor_minor is not None
            and self.negotiation_floor_minor > values[-1].unit_price_minor
        ):
            raise ValueError(
                "Negotiation floor cannot exceed the lowest published tier"
            )
        if self.image_url and not self.image_url.startswith("https://"):
            raise ValueError("Product images require an HTTPS URL")
        if self.product_url and not self.product_url.startswith("https://"):
            raise ValueError("Public product pages require an HTTPS URL")
        return self


class Zone(Input):
    currency: Literal["USD", "EUR", "GBP", "INR"] = "USD"
    name: str = Field(min_length=2, max_length=100)
    polygon: list[tuple[float, float]] = Field(min_length=3, max_length=100)
    depot: tuple[float, float]
    base_freight_minor: int = Field(ge=0, le=10000000)
    stop_fee_minor: int = Field(ge=0, le=1000000)
    min_weight_grams: int = Field(default=0, ge=0)
    max_weight_grams: int = Field(default=500000, gt=0)
    max_volume_cm3: int = Field(default=1000000, gt=0)
    active: bool = True
    freight_weight_percent: int = Field(default=50, ge=0, le=100)
    timezone: str = "Asia/Kolkata"
    dispatch_time: str = "09:00"
    delivery_window: str = Field(default="09:00–18:00", max_length=100)
    weekdays: list[int] = Field(
        default_factory=lambda: list(range(7)), min_length=1, max_length=7
    )
    cutoff_hours_before: int = Field(default=0, ge=0, le=336)
    auto_clear_at_cutoff: bool = True
    recipient_confirmation_required: bool = False
    approval_hours: int = Field(default=24, ge=1, le=72)

    @model_validator(mode="after")
    def geometry(self):
        from datetime import time
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(self.timezone)
            time.fromisoformat(self.dispatch_time)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("Use a valid IANA timezone and dispatch time")
        if any(day not in range(7) for day in self.weekdays) or len(
            set(self.weekdays)
        ) != len(self.weekdays):
            raise ValueError("Weekdays must be unique integers from 0 (Monday) to 6")
        if self.polygon[0] == self.polygon[-1]:
            self.polygon = self.polygon[:-1]
        if len(set(self.polygon)) != len(self.polygon) or len(self.polygon) < 3:
            raise ValueError("A polygon requires at least three distinct vertices")
        for lon, lat in [*self.polygon, self.depot]:
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise ValueError("coordinates must be longitude, latitude")
        if self.min_weight_grams > self.max_weight_grams:
            raise ValueError("minimum route weight exceeds capacity")
        area = sum(
            a[0] * b[1] - b[0] * a[1]
            for a, b in zip(self.polygon, self.polygon[1:] + self.polygon[:1])
        )
        if abs(area) < 1e-10:
            raise ValueError("delivery polygon must have nonzero area")
        edges = list(zip(self.polygon, self.polygon[1:] + self.polygon[:1]))

        def orient(a, b, c):
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        for i, (a, b) in enumerate(edges):
            for j, (c, d) in enumerate(edges):
                if j <= i + 1 or (i == 0 and j == len(edges) - 1):
                    continue
                if (
                    orient(a, b, c) * orient(a, b, d) <= 0
                    and orient(c, d, a) * orient(c, d, b) <= 0
                ):
                    if max(min(a[0], b[0]), min(c[0], d[0])) <= min(
                        max(a[0], b[0]), max(c[0], d[0])
                    ) and max(min(a[1], b[1]), min(c[1], d[1])) <= min(
                        max(a[1], b[1]), max(c[1], d[1])
                    ):
                        raise ValueError("Delivery polygon must not intersect itself")
        return self


class Request(Input):
    product_id: str
    zone_id: str
    dispatch_date: date
    quantity_min: int = Field(gt=0, le=5000)
    quantity_max: int = Field(gt=0, le=5000)
    ceiling_minor: int = Field(gt=0, le=100000000)
    substitute_product_ids: list[str] = Field(default_factory=list, max_length=2)
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def quantities(self):
        if self.quantity_min > self.quantity_max:
            raise ValueError("minimum quantity exceeds maximum")
        if (
            len(set(self.substitute_product_ids)) != len(self.substitute_product_ids)
            or self.product_id in self.substitute_product_ids
        ):
            raise ValueError(
                "Choose distinct substitute products different from the requested SKU"
            )
        return self


class Version(Input):
    version: int = Field(gt=0)


class Delivery(Input):
    delivered_quantity: int = Field(ge=0)
    recipient_name: str = Field(min_length=2, max_length=100)
    acknowledgement: bool
    exception: (
        Literal[
            "DAMAGED",
            "MISSING_ITEMS",
            "RECIPIENT_UNAVAILABLE",
            "REFUSED",
            "ADDRESS_ISSUE",
            "OTHER",
        ]
        | None
    ) = None
    note: str = Field(default="", max_length=1000)


class Refund(Input):
    amount_minor: int = Field(gt=0)
    reason: str = Field(min_length=3, max_length=200)


class Profile(Input):
    name: str = Field(min_length=2, max_length=200)
    location: tuple[float, float]


class Dispatch(Input):
    driver_id: str
    vehicle_id: str | None = None


class RoleGrant(Input):
    role: Literal["RETAILER", "SELLER", "DRIVER", "ADMIN"]


class Discovery(Input):
    message: str = Field(min_length=1, max_length=1000)
    currency: Literal["USD", "EUR", "GBP", "INR"] = "USD"


class Vehicle(Input):
    name: str = Field(min_length=2, max_length=100)
    registration: str = Field(min_length=2, max_length=40)
    max_weight_grams: int = Field(gt=0, le=100000000)
    max_volume_cm3: int = Field(gt=0, le=1000000000)
    active: bool = True


class InventoryChange(Input):
    product_id: str
    delta: int = Field(ge=-1000000, le=1000000)
    expected_stock: int = Field(ge=0)
    reason: str = Field(min_length=3, max_length=300)


class OfferTerms(Input):
    product_id: str
    quantity_min: int = Field(gt=0, le=5000)
    quantity_max: int = Field(gt=0, le=5000)
    unit_price_minor: int = Field(gt=0, le=100000000)
    expires_in_hours: int = Field(default=24, ge=1, le=168)
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def interval(self):
        if self.quantity_min > self.quantity_max:
            raise ValueError("Minimum quantity exceeds maximum")
        return self


class NewOffer(OfferTerms):
    request_id: str


class CounterOffer(OfferTerms):
    version: int = Field(gt=0)


class StandingOrder(Input):
    name: str = Field(min_length=2, max_length=100)
    request: Request
    repeat_days: int = Field(default=7, ge=1, le=90)
    lookahead_days: int = Field(default=7, ge=0, le=30)
    end_date: date | None = None


class StateChange(Input):
    active: bool


class ExceptionResolution(Input):
    action: Literal["VOID_AND_CLOSE", "REDELIVER"]
    reason: str = Field(min_length=3, max_length=500)
    returned_quantity: int = Field(default=0, ge=0)
    replacement_quantity: int = Field(default=0, ge=0, le=5000)


class AgentAccess(Input):
    name: str = Field(min_length=2, max_length=100)
    expires_in_hours: int = Field(default=8, ge=1, le=168)
