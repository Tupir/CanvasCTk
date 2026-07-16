from __future__ import annotations

from pathlib import Path

import customtkinter as ctk
from customtkinter.windows.widgets.scaling.scaling_tracker import ScalingTracker


THEME_PATH = Path(__file__).with_name("themes") / "canvas.json"


def setup(appearance: str = "System", theme: str | Path = THEME_PATH) -> None:
    """Load the bundled theme and select System, Light, or Dark appearance."""
    ctk.set_default_color_theme(str(theme))
    ctk.set_appearance_mode(appearance)


def set_widget_scaling(scaling_value: float) -> None:
    """Set the shared CustomTkinter/CanvasCTk widget scaling factor."""
    ctk.set_widget_scaling(scaling_value)


def get_widget_scaling(widget: object | None = None) -> float:
    """Return the active widget scaling, including the window DPI factor when available."""
    if widget is not None:
        target = getattr(widget, "canvas", widget)
        try:
            return float(ScalingTracker.get_widget_scaling(target))
        except (AttributeError, KeyError, TypeError):
            pass
    return float(ScalingTracker.widget_scaling)
