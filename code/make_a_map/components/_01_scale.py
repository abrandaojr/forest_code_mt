"""Projection-aware scale bar component."""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from pyproj import CRS

from .._00_theme import Theme


def draw_scale_bar(
    ax: plt.Axes, crs: str, label: str, theme: Theme, length_m: int = 500_000
) -> None:
    parsed = CRS.from_user_input(crs)
    if not parsed.is_projected:
        raise ValueError("scale bars require a projected CRS")
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    x0 = xmin + (xmax - xmin) * 0.065
    y0 = ymin + (ymax - ymin) * 0.08
    height = (ymax - ymin) * 0.009
    half = length_m / 2
    ax.add_patch(Rectangle((x0, y0), half, height, color=theme.colors.ink, zorder=8))
    ax.add_patch(
        Rectangle(
            (x0 + half, y0),
            half,
            height,
            facecolor=theme.colors.paper,
            edgecolor=theme.colors.ink,
            linewidth=theme.strokes.context,
            zorder=8,
        )
    )
    ax.text(
        x0 + half,
        y0 + height * 2.1,
        label,
        ha="center",
        va="bottom",
        fontsize=theme.typography.body_size,
        color=theme.colors.ink,
        zorder=8,
    )
