"""Small, explicit layout grammar for the 7.5-inch square master."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LayoutRecipe = Literal["single-focus", "map-plus-metric", "map-plus-legend", "dense-choropleth"]


@dataclass(frozen=True, slots=True)
class Box:
    left: float
    bottom: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def top(self) -> float:
        return self.bottom + self.height

    def overlaps(self, other: Box, tolerance: float = 1e-9) -> bool:
        return not (
            self.right <= other.left + tolerance
            or other.right <= self.left + tolerance
            or self.top <= other.bottom + tolerance
            or other.top <= self.bottom + tolerance
        )


@dataclass(frozen=True, slots=True)
class LayoutSlots:
    name: LayoutRecipe
    header: Box
    map_body: Box
    rail: Box
    globe: Box
    source: Box

    def validate(self) -> None:
        named = {
            "header": self.header,
            "map_body": self.map_body,
            "rail": self.rail,
            "globe": self.globe,
            "source": self.source,
        }
        for name, box in named.items():
            if min(box.left, box.bottom, box.width, box.height) < 0:
                raise ValueError(f"layout slot {name} has a negative value")
            if box.right > 1 or box.top > 1:
                raise ValueError(f"layout slot {name} leaves the figure")
        protected_pairs = (("header", "map_body"), ("header", "rail"), ("source", "map_body"))
        for first, second in protected_pairs:
            if named[first].overlaps(named[second]):
                raise ValueError(f"layout slots overlap: {first} and {second}")


MAP_PLUS_METRIC = LayoutSlots(
    name="map-plus-metric",
    header=Box(0.055, 0.78, 0.89, 0.17),
    map_body=Box(0.055, 0.16, 0.65, 0.60),
    rail=Box(0.715, 0.40, 0.235, 0.34),
    globe=Box(0.765, 0.205, 0.17, 0.17),
    source=Box(0.055, 0.025, 0.89, 0.07),
)

SINGLE_FOCUS = LayoutSlots(
    name="single-focus",
    header=Box(0.055, 0.78, 0.89, 0.17),
    map_body=Box(0.055, 0.14, 0.78, 0.62),
    rail=Box(0.84, 0.42, 0.105, 0.28),
    globe=Box(0.79, 0.20, 0.15, 0.15),
    source=Box(0.055, 0.025, 0.89, 0.07),
)

LAYOUTS: dict[LayoutRecipe, LayoutSlots] = {
    "single-focus": SINGLE_FOCUS,
    "map-plus-metric": MAP_PLUS_METRIC,
    "map-plus-legend": MAP_PLUS_METRIC,
    "dense-choropleth": MAP_PLUS_METRIC,
}


def get_layout(name: LayoutRecipe) -> LayoutSlots:
    layout = LAYOUTS[name]
    layout.validate()
    return layout
