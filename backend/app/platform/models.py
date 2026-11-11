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

    @model_validator(mode="after")
    def geometry(self):
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


class RoleGrant(Input):
    role: Literal["RETAILER", "SELLER", "DRIVER", "ADMIN"]


class Discovery(Input):
    message: str = Field(min_length=1, max_length=1000)
    currency: Literal["USD", "EUR", "GBP", "INR"] = "USD"
