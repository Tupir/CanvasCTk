from __future__ import annotations

import sys
import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ._ctk_port import CanvasCTkWidget


class Scrollbar(CanvasCTkWidget):
    """Canvas-backed port of ``customtkinter.CTkScrollbar``."""

    def __init__(
        self,
        master: Any,
        width: int | None = None,
        height: int | None = None,
        corner_radius: int | None = None,
        border_spacing: int | None = None,
        minimum_pixel_length: int = 20,
        bg_color: Any = "transparent",
        fg_color: Any = None,
        button_color: Any = None,
        button_hover_color: Any = None,
        hover: bool = True,
        command: Callable[..., Any] | None = None,
        orientation: str = "vertical",
        *,
        canvas: tk.Canvas | None = None,
        x: int = 0,
        y: int = 0,
        **kwargs: Any,
    ) -> None:
        orientation = str(orientation).lower()
        if orientation not in ("horizontal", "vertical"):
            raise ValueError("orientation must be 'horizontal' or 'vertical'")
        if width is None:
            width = 16 if orientation == "vertical" else 200
        if height is None:
            height = 16 if orientation == "horizontal" else 200

        # Unlike a standalone Tk widget, CanvasCTk controls share their
        # master's canvas.  Remember whether the caller requested a genuinely
        # transparent background so the scrollbar track does not paint an
        # opaque parent-coloured strip over sibling canvas content.
        self._bg_is_transparent = bg_color == "transparent"
        super().__init__(
            master,
            width=width,
            height=height,
            bg_color=bg_color,
            canvas=canvas,
            x=x,
            y=y,
            **kwargs,
        )
        theme = ctk.ThemeManager.theme["CTkScrollbar"]
        self._fg_color = self._check_color_type(
            theme["fg_color"] if fg_color is None else fg_color,
            transparency=True,
        )
        self._button_color = self._check_color_type(
            theme["button_color"] if button_color is None else button_color,
        )
        self._button_hover_color = self._check_color_type(
            theme["button_hover_color"] if button_hover_color is None else button_hover_color,
        )
        self._corner_radius = int(theme["corner_radius"] if corner_radius is None else corner_radius)
        self._border_spacing = int(theme["border_spacing"] if border_spacing is None else border_spacing)
        self._track_theme_defaults(
            "CTkScrollbar",
            fg_color=fg_color is None,
            button_color=button_color is None,
            button_hover_color=button_hover_color is None,
            corner_radius=corner_radius is None,
            border_spacing=border_spacing is None,
        )
        self._minimum_pixel_length = max(0, int(minimum_pixel_length))
        self._hover = bool(hover)
        self._hover_state = False
        self._command = command
        self._orientation = orientation
        self._start_value = 0.0
        self._end_value = 1.0

        self._create_bindings()
        self._draw()

    def _create_bindings(self, sequence: str | None = None) -> None:
        if sequence is None or sequence == "<Button-1>":
            self._canvas.tag_bind("border_parts", "<Button-1>", self._clicked)
        if sequence is None or sequence == "<Enter>":
            self._canvas.bind("<Enter>", self._on_enter, add=True)
        if sequence is None or sequence == "<Leave>":
            self._canvas.bind("<Leave>", self._on_leave, add=True)
        if sequence is None or sequence == "<B1-Motion>":
            self._canvas.bind("<B1-Motion>", self._clicked, add=True)

    def _background_fill(self) -> Any:
        if self._bg_is_transparent:
            return ""
        if self._bg_color != "transparent":
            return self._apply_appearance_mode(self._bg_color)
        parent = self.master
        while parent is not None:
            try:
                color = parent.cget("fg_color")
                if color not in (None, "transparent"):
                    return self._apply_appearance_mode(color)
            except Exception:
                pass
            parent = getattr(parent, "master", None)
        return self.canvas.cget("bg")

    def _get_scrollbar_values_for_minimum_pixel_size(self) -> tuple[float, float]:
        length = self._current_height if self._orientation == "vertical" else self._current_width
        scrollbar_pixel_length = (self._end_value - self._start_value) * length
        if scrollbar_pixel_length >= self._minimum_pixel_length or length == scrollbar_pixel_length:
            return self._start_value, self._end_value
        extend = (-scrollbar_pixel_length + self._minimum_pixel_length) / (-scrollbar_pixel_length + length)
        return (
            self._start_value - self._start_value * extend,
            self._end_value + (1 - self._end_value) * extend,
        )

    def _draw(self, no_color_updates: bool = False) -> None:
        start, end = self._get_scrollbar_values_for_minimum_pixel_size()
        requires_recoloring = self._draw_engine.draw_rounded_scrollbar(
            self._current_width,
            self._current_height,
            self._corner_radius,
            self._border_spacing,
            start,
            end,
            self._orientation,
        )
        if no_color_updates and not requires_recoloring:
            return
        self._refresh_thumb_color()
        self._refresh_track_color()

    def _refresh_thumb_color(self) -> None:
        thumb_color = self._button_hover_color if self._hover_state else self._button_color
        thumb_color = self._apply_appearance_mode(thumb_color)
        self._canvas.itemconfig("scrollbar_parts", fill=thumb_color, outline=thumb_color)

    def _refresh_track_color(self) -> None:
        if self._fg_color == "transparent":
            track_color = "" if self._bg_is_transparent else self._background_fill()
        else:
            track_color = self._apply_appearance_mode(self._fg_color)
        self._canvas.itemconfig("border_parts", fill=track_color, outline=track_color)

    def _on_enter(self, _: Any = None) -> None:
        if self._hover and not self._hover_state:
            self._hover_state = True
            self._refresh_thumb_color()

    def _on_leave(self, _: Any = None) -> None:
        if not self._hover_state:
            return
        self._hover_state = False
        self._refresh_thumb_color()

    def _clicked(self, event: Any) -> None:
        available = (self._current_height if self._orientation == "vertical" else self._current_width) - 2 * self._border_spacing
        if available <= 0:
            return
        coordinate = event.y if self._orientation == "vertical" else event.x
        value = (coordinate - self._border_spacing) / available
        length = self._end_value - self._start_value
        value = max(length / 2, min(value, 1 - length / 2))
        self._start_value = value - length / 2
        self._end_value = value + length / 2
        self._draw(no_color_updates=True)
        if self._command is not None:
            self._command("moveto", self._start_value)

    def _mouse_scroll_event(self, event: Any = None) -> None:
        if self._command is None or event is None:
            return
        if sys.platform.startswith("win"):
            self._command("scroll", -int(event.delta / 40), "units")
        else:
            self._command("scroll", -event.delta, "units")

    def set(self, start_value: float, end_value: float) -> None:
        start_value = float(start_value)
        end_value = float(end_value)
        if (start_value, end_value) == (self._start_value, self._end_value):
            return
        self._start_value = start_value
        self._end_value = end_value
        self._draw(no_color_updates=True)

    def get(self) -> tuple[float, float]:
        return self._start_value, self._end_value

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        refresh_track = False
        refresh_thumb = False
        if "bg_color" in kwargs:
            self._bg_is_transparent = kwargs["bg_color"] == "transparent"
            refresh_track = True
        if "fg_color" in kwargs:
            self._fg_color = self._check_color_type(kwargs.pop("fg_color"), transparency=True)
            refresh_track = True
        if "button_color" in kwargs or "scrollbar_color" in kwargs:
            self._button_color = self._check_color_type(kwargs.pop("button_color", kwargs.pop("scrollbar_color", None)))
            refresh_thumb = True
        if "button_hover_color" in kwargs or "scrollbar_hover_color" in kwargs:
            self._button_hover_color = self._check_color_type(kwargs.pop("button_hover_color", kwargs.pop("scrollbar_hover_color", None)))
            refresh_thumb = True
        if "hover" in kwargs:
            self._hover = bool(kwargs.pop("hover"))
            if not self._hover:
                self._hover_state = False
                refresh_thumb = True
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if "corner_radius" in kwargs:
            self._corner_radius = int(kwargs.pop("corner_radius"))
            require_redraw = True
        if "border_spacing" in kwargs:
            self._border_spacing = int(kwargs.pop("border_spacing"))
            require_redraw = True
        if "minimum_pixel_length" in kwargs:
            self._minimum_pixel_length = max(0, int(kwargs.pop("minimum_pixel_length")))
            require_redraw = True
        if "orientation" in kwargs:
            orientation = str(kwargs.pop("orientation")).lower()
            if orientation not in ("horizontal", "vertical"):
                raise ValueError("orientation must be 'horizontal' or 'vertical'")
            self._orientation = orientation
            require_redraw = True
        super().configure(require_redraw=require_redraw, **kwargs)
        if not require_redraw:
            if refresh_track:
                self._refresh_track_color()
            if refresh_thumb:
                self._refresh_thumb_color()

    config = configure

    def cget(self, attribute_name: str) -> Any:
        values = {
            "corner_radius": self._corner_radius,
            "border_spacing": self._border_spacing,
            "minimum_pixel_length": self._minimum_pixel_length,
            "fg_color": self._fg_color,
            "button_color": self._button_color,
            "scrollbar_color": self._button_color,
            "button_hover_color": self._button_hover_color,
            "scrollbar_hover_color": self._button_hover_color,
            "hover": self._hover,
            "command": self._command,
            "orientation": self._orientation,
        }
        return values[attribute_name] if attribute_name in values else super().cget(attribute_name)


__all__ = ["Scrollbar"]
