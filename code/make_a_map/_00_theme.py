"""Versioned semantic design tokens; map subjects never appear here."""

from __future__ import annotations

from dataclasses import dataclass, field


def _hex(name: str, value: str) -> None:
    if len(value) != 7 or not value.startswith("#"):
        raise ValueError(f"{name} must be a six-digit hex color")
    try:
        int(value[1:], 16)
    except ValueError as exc:
        raise ValueError(f"{name} must be a six-digit hex color") from exc


@dataclass(frozen=True, slots=True)
class ColorTokens:
    paper: str = "#F7F4EE"
    ink: str = "#222222"
    muted_ink: str = "#6E6D68"
    context_fill: str = "#DDDCD6"
    context_line: str = "#B9B8B2"
    boundary_light: str = "#FFFFFF"
    data_primary: str = "#1E786A"
    data_primary_edge: str = "#11574D"
    data_accent: str = "#D67C42"
    water: str = "#DDE8E6"
    graticule: str = "#A9BEBA"

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            _hex(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class TypographyTokens:
    # DejaVu Sans ships with Matplotlib, covers pt-BR glyphs and avoids host fallback.
    family: tuple[str, ...] = ("DejaVu Sans",)
    title_size: float = 19.0
    subtitle_size: float = 10.5
    body_size: float = 9.0
    note_size: float = 7.0

    def __post_init__(self) -> None:
        if not self.family or any(not item.strip() for item in self.family):
            raise ValueError("font family stack cannot be empty")
        for name in ("title_size", "subtitle_size", "body_size", "note_size"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")


@dataclass(frozen=True, slots=True)
class StrokeTokens:
    hairline: float = 0.35
    context: float = 0.75
    emphasis: float = 1.25

    def __post_init__(self) -> None:
        if not (0 < self.hairline <= self.context <= self.emphasis):
            raise ValueError(
                "stroke widths must be positive and ordered hairline <= context <= emphasis"
            )


@dataclass(frozen=True, slots=True)
class SpacingTokens:
    xs: float = 0.008
    sm: float = 0.016
    md: float = 0.032
    lg: float = 0.055

    def __post_init__(self) -> None:
        if not (0 < self.xs < self.sm < self.md < self.lg < 1):
            raise ValueError("spacing tokens must increase and use figure-relative values below 1")


@dataclass(frozen=True, slots=True)
class Theme:
    version: str = "1.0"
    colors: ColorTokens = field(default_factory=ColorTokens)
    typography: TypographyTokens = field(default_factory=TypographyTokens)
    strokes: StrokeTokens = field(default_factory=StrokeTokens)
    spacing: SpacingTokens = field(default_factory=SpacingTokens)

    def __post_init__(self) -> None:
        if not self.version or not all(part.isdigit() for part in self.version.split(".")):
            raise ValueError("theme version must be numeric and dotted")


DEFAULT_THEME = Theme()
