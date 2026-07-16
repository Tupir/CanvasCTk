from __future__ import annotations

import time
from typing import Any, Callable

import customtkinter as ctk


def ease_out_cubic(t: float) -> float:
    return 1 - pow(1 - t, 3)


def ease_in_out_cubic(t: float) -> float:
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


def linear(t: float) -> float:
    return t


EASINGS = {
    "linear": linear,
    "ease_out": ease_out_cubic,
    "ease_in_out": ease_in_out_cubic,
}


def _resolve_color(color: Any) -> Any:
    if isinstance(color, tuple):
        return color[1] if ctk.get_appearance_mode().lower() == "dark" else color[0]
    return color


def _rgb(widget: Any, color: Any) -> tuple[int, int, int]:
    red, green, blue = widget.winfo_rgb(_resolve_color(color))
    return red // 256, green // 256, blue // 256


def _mix_color(widget: Any, start: Any, end: Any, progress: float) -> str:
    start_red, start_green, start_blue = _rgb(widget, start)
    end_red, end_green, end_blue = _rgb(widget, end)
    red = int(start_red + (end_red - start_red) * progress)
    green = int(start_green + (end_green - start_green) * progress)
    blue = int(start_blue + (end_blue - start_blue) * progress)
    return f"#{red:02x}{green:02x}{blue:02x}"


class TweenState:
    def __init__(self) -> None:
        self.finished = False
        self.cancelled = False
        self.progress = 0.0


def Tween(
    widget: Any,
    duration: float = 3,
    easing: str = "ease_out",
    on_finish: Callable[[], Any] | None = None,
    **targets: Any,
) -> TweenState:
    """Animate CanvasCTk geometry and configuration values."""
    if not hasattr(widget, "_tween_after_id"):
        widget._tween_after_id = None
    if not hasattr(widget, "_tween_state"):
        widget._tween_state = None

    if widget._tween_after_id is not None:
        try:
            widget.after_cancel(widget._tween_after_id)
        except Exception:
            pass
    if widget._tween_state is not None:
        widget._tween_state.cancelled = True

    state = TweenState()
    widget._tween_state = state
    easing_func = EASINGS.get(easing, ease_out_cubic)
    place_keys = {"x", "y", "relx", "rely", "anchor"}
    color_keys = {"fg_color", "text_color", "border_color", "hover_color"}
    start_values: dict[str, Any] = {}
    place_info = widget.place_info()

    for key, target in targets.items():
        if key in place_keys:
            start_values[key] = target if key == "anchor" else float(place_info.get(key, 0) or 0)
        else:
            try:
                start_values[key] = widget.cget(key)
            except Exception:
                start_values[key] = target

    start_time = time.perf_counter()
    duration = max(0.000001, float(duration))

    def update() -> None:
        if state.cancelled:
            return
        progress = min((time.perf_counter() - start_time) / duration, 1.0)
        state.progress = progress
        eased = easing_func(progress)
        place_updates: dict[str, Any] = {}
        config_updates: dict[str, Any] = {}

        for key, target in targets.items():
            start = start_values[key]
            if key == "anchor":
                place_updates[key] = target
                continue
            if key in color_keys:
                value = _mix_color(widget, start, target, eased)
            else:
                try:
                    value = float(start) + (float(target) - float(start)) * eased
                    if key in {"x", "y", "width", "height", "corner_radius", "border_width"}:
                        value = int(value)
                except Exception:
                    value = target
            if key in place_keys:
                place_updates[key] = value
            else:
                config_updates[key] = value

        if place_updates:
            widget.place_configure(**place_updates)
        if config_updates:
            widget.configure(**config_updates)
        if progress < 1:
            widget._tween_after_id = widget.after(16, update)
            return

        state.finished = True
        widget._tween_after_id = None
        if on_finish is not None:
            on_finish()

    update()
    return state


__all__ = [
    "EASINGS",
    "Tween",
    "TweenState",
    "ease_in_out_cubic",
    "ease_out_cubic",
    "linear",
]
