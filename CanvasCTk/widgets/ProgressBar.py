from __future__ import annotations

import math
import tkinter as tk
from typing import Any

import customtkinter as ctk

from ._ctk_port import CanvasCTkWidget


class ProgressBar(CanvasCTkWidget):
    """Canvas-backed port of ``customtkinter.CTkProgressBar``."""

    def __init__(
        self,
        master: Any,
        width: int | None = None,
        height: int | None = None,
        corner_radius: int | None = None,
        border_width: int | None = None,
        bg_color: Any = "transparent",
        fg_color: Any = None,
        border_color: Any = None,
        progress_color: Any = None,
        variable: tk.Variable | None = None,
        orientation: str = "horizontal",
        mode: str = "determinate",
        determinate_speed: float = 1,
        indeterminate_speed: float = 1,
        *,
        canvas: tk.Canvas | None = None,
        x: int = 0,
        y: int = 0,
        **kwargs: Any,
    ) -> None:
        orientation = str(orientation).lower()
        if orientation not in ("horizontal", "vertical"):
            raise ValueError("orientation must be 'horizontal' or 'vertical'")
        if mode not in ("determinate", "indeterminate"):
            raise ValueError("mode must be 'determinate' or 'indeterminate'")
        if width is None:
            width = 8 if orientation == "vertical" else 200
        if height is None:
            height = 200 if orientation == "vertical" else 8

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
        theme = ctk.ThemeManager.theme["CTkProgressBar"]
        self._border_color = self._check_color_type(
            theme["border_color"] if border_color is None else border_color,
            transparency=True,
        )
        self._fg_color = self._check_color_type(
            theme["fg_color"] if fg_color is None else fg_color,
        )
        self._progress_color = self._check_color_type(
            theme["progress_color"] if progress_color is None else progress_color,
            transparency=True,
        )
        self._corner_radius = int(theme["corner_radius"] if corner_radius is None else corner_radius)
        self._border_width = int(theme["border_width"] if border_width is None else border_width)
        self._track_theme_defaults(
            "CTkProgressBar",
            border_color=border_color is None,
            fg_color=fg_color is None,
            progress_color=progress_color is None,
            corner_radius=corner_radius is None,
            border_width=border_width is None,
        )
        self._variable = variable
        self._variable_callback_blocked = False
        self._orientation = orientation
        self._mode = mode
        self._determinate_speed = float(determinate_speed)
        self._indeterminate_speed = float(indeterminate_speed)
        self._determinate_value = 0.5
        self._indeterminate_value = 0.0
        self._indeterminate_width = 0.4
        self._loop_running = False
        self._loop_after_id: str | None = None

        if self._variable is not None and self._variable != "":
            self.trace_write(self._variable, self._variable_changed)
            self.set(self._variable.get(), from_variable_callback=True)
        self._draw()

    def _background_fill(self) -> Any:
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

    def _draw(self, no_color_updates: bool = False) -> None:
        orientation = "w" if self._orientation == "horizontal" else "s"
        if self._mode == "determinate":
            requires_recoloring = self._draw_engine.draw_rounded_progress_bar_with_border(
                self._current_width,
                self._current_height,
                self._corner_radius,
                self._border_width,
                0,
                self._determinate_value,
                orientation,
            )
        else:
            progress_value = (math.sin(self._indeterminate_value * math.pi / 40) + 1) / 2
            progress_value_1 = min(1.0, progress_value + self._indeterminate_width / 2)
            progress_value_2 = max(0.0, progress_value - self._indeterminate_width / 2)
            requires_recoloring = self._draw_engine.draw_rounded_progress_bar_with_border(
                self._current_width,
                self._current_height,
                self._corner_radius,
                self._border_width,
                progress_value_1,
                progress_value_2,
                orientation,
            )

        if no_color_updates and not requires_recoloring:
            return
        self._refresh_colors()

    def _refresh_colors(self) -> None:
        border = self._background_fill() if self._border_color == "transparent" else self._apply_appearance_mode(self._border_color)
        foreground = self._apply_appearance_mode(self._fg_color)
        progress = foreground if self._progress_color == "transparent" else self._apply_appearance_mode(self._progress_color)
        self._canvas.itemconfig("border_parts", fill=border, outline=border)
        self._canvas.itemconfig("inner_parts", fill=foreground, outline=foreground)
        self._canvas.itemconfig("progress_parts", fill=progress, outline=progress)
        self._canvas.tag_raise("progress_parts", "inner_parts")

    def _variable_changed(self, _: Any, value: Any) -> None:
        if not self._variable_callback_blocked:
            self.set(value, from_variable_callback=True)

    def set(self, value: float, from_variable_callback: bool = False) -> None:
        value = max(0.0, min(1.0, float(value)))
        if value != self._determinate_value:
            self._determinate_value = value
            self._draw(no_color_updates=True)
        if self._variable is not None and not from_variable_callback:
            self._variable_callback_blocked = True
            self._variable.set(round(self._determinate_value) if isinstance(self._variable, tk.IntVar) else self._determinate_value)
            self._variable_callback_blocked = False

    def get(self) -> float:
        return self._determinate_value

    def start(self) -> None:
        if not self._loop_running:
            self._loop_running = True
            self._internal_loop()

    def stop(self) -> None:
        if self._loop_after_id is not None:
            try:
                self.after_cancel(self._loop_after_id)
            except tk.TclError:
                pass
            self._loop_after_id = None
        self._loop_running = False

    def _internal_loop(self) -> None:
        if not self._loop_running:
            return
        self.step()
        self._loop_after_id = self.after(20, self._internal_loop)

    def step(self) -> None:
        if self._mode == "determinate":
            self._determinate_value += self._determinate_speed / 50
            if self._determinate_value > 1:
                self._determinate_value -= 1
        else:
            self._indeterminate_value += self._indeterminate_speed
        self._draw(no_color_updates=True)

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        refresh_colors = False
        if "corner_radius" in kwargs:
            self._corner_radius = int(kwargs.pop("corner_radius"))
            require_redraw = True
        if "border_width" in kwargs:
            self._border_width = int(kwargs.pop("border_width"))
            require_redraw = True
        if "fg_color" in kwargs:
            self._fg_color = self._check_color_type(kwargs.pop("fg_color"))
            refresh_colors = True
        if "border_color" in kwargs:
            self._border_color = self._check_color_type(kwargs.pop("border_color"), transparency=True)
            refresh_colors = True
        if "progress_color" in kwargs:
            self._progress_color = self._check_color_type(kwargs.pop("progress_color"), transparency=True)
            refresh_colors = True
        if "variable" in kwargs:
            self.untrace_write()
            self._variable = kwargs.pop("variable")
            if self._variable is not None and self._variable != "":
                self.trace_write(self._variable, self._variable_changed)
                self.set(self._variable.get(), from_variable_callback=True)
            else:
                self._variable = None
        if "orientation" in kwargs:
            orientation = str(kwargs.pop("orientation")).lower()
            if orientation not in ("horizontal", "vertical"):
                raise ValueError("orientation must be 'horizontal' or 'vertical'")
            self._orientation = orientation
            require_redraw = True
        if "mode" in kwargs:
            mode = str(kwargs.pop("mode"))
            if mode not in ("determinate", "indeterminate"):
                raise ValueError("mode must be 'determinate' or 'indeterminate'")
            self._mode = mode
            require_redraw = True
        if "determinate_speed" in kwargs:
            self._determinate_speed = float(kwargs.pop("determinate_speed"))
        if "indeterminate_speed" in kwargs:
            self._indeterminate_speed = float(kwargs.pop("indeterminate_speed"))
        super().configure(require_redraw=require_redraw, **kwargs)
        if not require_redraw and refresh_colors:
            self._refresh_colors()

    config = configure

    def cget(self, attribute_name: str) -> Any:
        values = {
            "corner_radius": self._corner_radius,
            "border_width": self._border_width,
            "fg_color": self._fg_color,
            "border_color": self._border_color,
            "progress_color": self._progress_color,
            "variable": self._variable,
            "orientation": self._orientation,
            "mode": self._mode,
            "determinate_speed": self._determinate_speed,
            "indeterminate_speed": self._indeterminate_speed,
        }
        return values[attribute_name] if attribute_name in values else super().cget(attribute_name)

    def destroy(self) -> None:
        self.stop()
        super().destroy()


__all__ = ["ProgressBar"]
