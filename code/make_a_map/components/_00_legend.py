"""Compact, deterministic legend component."""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from .._00_theme import Theme


@dataclass(frozen=True, slots=True)
class LegendItem:
    label: str
    fill: str
    edge: str | None = None


def draw_legend(
    figure: plt.Figure, items: tuple[LegendItem, ...], anchor: tuple[float, float], theme: Theme
) -> None:
    if not 1 <= len(items) <= 7:
        raise ValueError("editorial legends require between 1 and 7 items")
    handles = [
        Rectangle((0, 0), 1, 1, facecolor=item.fill, edgecolor=item.edge or "none")
        for item in items
    ]
    figure.legend(
        handles,
        [item.label for item in items],
        loc="upper left",
        bbox_to_anchor=anchor,
        frameon=False,
        fontsize=theme.typography.body_size,
        handlelength=1.2,
        handleheight=1.2,
        labelspacing=0.9,
    )
