from __future__ import annotations

import sys
import tkinter as tk
from typing import Any, Callable

import customtkinter as ctk

from ._ctk_port import CanvasCTkWidget


class Slider(CanvasCTkWidget):
    """Canvas port of CustomTkinter's ``CTkSlider`` drawing and interaction model."""

    def __init__(
        self,
        master: Any,
        width: int | None = None,
        height: int | None = None,
        corner_radius: int | None = None,
        button_corner_radius: int | None = None,
        border_width: int | None = None,
        button_length: int | None = None,
        bg_color: Any = "transparent",
        fg_color: Any = None,
        border_color: Any = "transparent",
        progress_color: Any = None,
        button_color: Any = None,
        button_hover_color: Any = None,
        from_: float = 0,
        to: float = 1,
        state: str = tk.NORMAL,
        number_of_steps: int | None = None,
        hover: bool = True,
        command: Callable[[float], Any] | None = None,
        variable: tk.Variable | None = None,
        orientation: str = "horizontal",
        *,
        canvas: tk.Canvas | None = None,
        x: int = 0,
        y: int = 0,
        **kwargs: Any,
    ) -> None:
        if width is None:
            width = 16 if orientation.lower() == "vertical" else 200
        if height is None:
            height = 200 if orientation.lower() == "vertical" else 16
        super().__init__(master, width=width, height=height, bg_color=bg_color, canvas=canvas, x=x, y=y, **kwargs)

        theme = ctk.ThemeManager.theme["CTkSlider"]
        self._border_color = self._check_color_type(border_color, transparency=True)
        self._fg_color = theme["fg_color"] if fg_color is None else self._check_color_type(fg_color)
        self._progress_color = theme["progress_color"] if progress_color is None else self._check_color_type(progress_color, transparency=True)
        self._button_color = theme["button_color"] if button_color is None else self._check_color_type(button_color)
        self._button_hover_color = theme["button_hover_color"] if button_hover_color is None else self._check_color_type(button_hover_color)
        self._corner_radius = theme["corner_radius"] if corner_radius is None else corner_radius
        self._button_corner_radius = theme["button_corner_radius"] if button_corner_radius is None else button_corner_radius
        self._border_width = theme["border_width"] if border_width is None else border_width
        self._button_length = theme["button_length"] if button_length is None else button_length
        self._track_theme_defaults(
            "CTkSlider",
            fg_color=fg_color is None,
            progress_color=progress_color is None,
            button_color=button_color is None,
            button_hover_color=button_hover_color is None,
            corner_radius=corner_radius is None,
            button_corner_radius=button_corner_radius is None,
            border_width=border_width is None,
            button_length=button_length is None,
        )
        self._value = 0.5
        self._orientation = orientation
        self._hover_state = False
        self._hover = bool(hover)
        self._from_ = from_
        self._to = to
        self._number_of_steps = number_of_steps
        self._output_value = self._from_ + self._value * (self._to - self._from_)
        if self._corner_radius < self._button_corner_radius:
            self._corner_radius = self._button_corner_radius
        self._command = command
        self._variable = variable
        self._variable_callback_blocked = False
        self._variable_callback_name: str | None = None
        self._state = state

        self._create_bindings()
        self._set_cursor()
        self._draw()
        if self._variable is not None:
            self._variable_callback_name = self._variable.trace_add("write", self._variable_callback)
            self._variable_callback_blocked = True
            self.set(self._variable.get(), from_variable_callback=True)
            self._variable_callback_blocked = False

    def _create_bindings(self, sequence: str | None = None) -> None:
        if sequence is None or sequence == "<Enter>":
            self._canvas.bind("<Enter>", self._on_enter, add="+")
        if sequence is None or sequence == "<Leave>":
            self._canvas.bind("<Leave>", self._on_leave, add="+")
        if sequence is None or sequence == "<Button-1>":
            self._canvas.bind("<Button-1>", self._clicked, add="+")
        if sequence is None or sequence == "<B1-Motion>":
            self._canvas.bind("<B1-Motion>", self._clicked, add="+")

    def _set_cursor(self) -> None:
        if not self._cursor_manipulation_enabled:
            return
        if self._state == tk.NORMAL:
            self.canvas.configure(cursor="pointinghand" if sys.platform == "darwin" else "hand2")
        else:
            self.canvas.configure(cursor="arrow")

    def _draw(self, no_color_updates: bool = False) -> None:
        orientation = "w" if self._orientation.lower() == "horizontal" else "s"
        requires_recoloring = self._draw_engine.draw_rounded_slider_with_border_and_button(
            self._current_width,
            self._current_height,
            self._corner_radius,
            self._border_width,
            self._button_length,
            self._button_corner_radius,
            self._value,
            orientation,
        )
        if no_color_updates and not requires_recoloring:
            return
        self._refresh_track_colors()

    def _refresh_track_colors(self) -> None:
        if self._border_color == "transparent":
            border_color = self._apply_appearance_mode(self._bg_color)
        else:
            border_color = self._apply_appearance_mode(self._border_color)
        self._canvas.itemconfig("border_parts", fill=border_color, outline=border_color)
        foreground = self._apply_appearance_mode(self._fg_color)
        self._canvas.itemconfig("inner_parts", fill=foreground, outline=foreground)
        progress = foreground if self._progress_color == "transparent" else self._apply_appearance_mode(self._progress_color)
        self._canvas.itemconfig("progress_parts", fill=progress, outline=progress)
        self._refresh_button_color()
        # DrawEngine's font renderer creates the rail after progress parts. Keep
        # the layers local to this shared canvas widget instead of lowering them
        # behind the parent Frame.
        self._canvas.tag_raise("progress_parts", "inner_parts")
        self._canvas.tag_raise("slider_parts", "progress_parts")

    def _refresh_button_color(self) -> None:
        button = self._button_hover_color if self._hover_state else self._button_color
        button = self._apply_appearance_mode(button)
        self._canvas.itemconfig("slider_parts", fill=button, outline=button)

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        refresh_track = False
        refresh_button = False
        if "corner_radius" in kwargs:
            self._corner_radius = kwargs.pop("corner_radius")
            require_redraw = True
        if "button_corner_radius" in kwargs:
            self._button_corner_radius = kwargs.pop("button_corner_radius")
            require_redraw = True
        if "border_width" in kwargs:
            self._border_width = kwargs.pop("border_width")
            require_redraw = True
        if "button_length" in kwargs:
            self._button_length = kwargs.pop("button_length")
            require_redraw = True
        for option in ("fg_color", "border_color", "progress_color", "button_color", "button_hover_color"):
            if option in kwargs:
                transparency = option in ("border_color", "progress_color")
                setattr(self, f"_{option}", self._check_color_type(kwargs.pop(option), transparency=transparency))
                if option in {"button_color", "button_hover_color"}:
                    refresh_button = True
                else:
                    refresh_track = True
        if "from_" in kwargs:
            self._from_ = kwargs.pop("from_")
        if "to" in kwargs:
            self._to = kwargs.pop("to")
        if "state" in kwargs:
            self._state = kwargs.pop("state")
            self._set_cursor()
            if self._state != tk.NORMAL and self._hover_state:
                self._hover_state = False
                refresh_button = True
        if "number_of_steps" in kwargs:
            self._number_of_steps = kwargs.pop("number_of_steps")
        if "hover" in kwargs:
            self._hover = bool(kwargs.pop("hover"))
            if not self._hover and self._hover_state:
                self._hover_state = False
                refresh_button = True
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if "variable" in kwargs:
            if self._variable is not None and self._variable_callback_name is not None:
                self._variable.trace_remove("write", self._variable_callback_name)
            self._variable = kwargs.pop("variable")
            self._variable_callback_name = None
            if self._variable is not None and self._variable != "":
                self._variable_callback_name = self._variable.trace_add("write", self._variable_callback)
                self.set(self._variable.get(), from_variable_callback=True)
            else:
                self._variable = None
        if "orientation" in kwargs:
            self._orientation = kwargs.pop("orientation")
            require_redraw = True
        super().configure(require_redraw=require_redraw, **kwargs)
        if not require_redraw:
            if refresh_track:
                self._refresh_track_colors()
            elif refresh_button:
                self._refresh_button_color()

    config = configure

    def cget(self, attribute_name: str) -> Any:
        values = {
            "corner_radius": self._corner_radius,
            "button_corner_radius": self._button_corner_radius,
            "border_width": self._border_width,
            "button_length": self._button_length,
            "fg_color": self._fg_color,
            "border_color": self._border_color,
            "progress_color": self._progress_color,
            "button_color": self._button_color,
            "button_hover_color": self._button_hover_color,
            "from_": self._from_,
            "to": self._to,
            "state": self._state,
            "number_of_steps": self._number_of_steps,
            "hover": self._hover,
            "command": self._command,
            "variable": self._variable,
            "orientation": self._orientation,
        }
        return values[attribute_name] if attribute_name in values else super().cget(attribute_name)

    def _clicked(self, event: Any = None) -> None:
        if self._state != tk.NORMAL or event is None:
            return
        if self._orientation.lower() == "horizontal":
            self._value = event.x / max(1, self._current_width)
        else:
            self._value = 1 - event.y / max(1, self._current_height)
        self._value = max(0.0, min(1.0, self._value))
        self._output_value = self._round_to_step_size(self._from_ + self._value * (self._to - self._from_))
        if self._to != self._from_:
            self._value = (self._output_value - self._from_) / (self._to - self._from_)
        self._draw(no_color_updates=True)
        if self._variable is not None:
            self._variable_callback_blocked = True
            self._variable.set(round(self._output_value) if isinstance(self._variable, tk.IntVar) else self._output_value)
            self._variable_callback_blocked = False
        if self._command is not None:
            self._command(self._output_value)

    def _on_enter(self, _event: Any = None) -> None:
        if self._hover and self._state == tk.NORMAL and not self._hover_state:
            self._hover_state = True
            self._refresh_button_color()

    def _on_leave(self, _event: Any = None) -> None:
        if not self._hover_state:
            return
        self._hover_state = False
        self._refresh_button_color()

    def _round_to_step_size(self, value: float) -> float:
        if self._number_of_steps is None:
            return value
        step_size = (self._to - self._from_) / self._number_of_steps
        return self._to - round((self._to - value) / step_size) * step_size

    def get(self) -> float:
        return self._output_value

    def set(self, output_value: float, from_variable_callback: bool = False) -> None:
        previous_value = self._value
        minimum, maximum = sorted((self._from_, self._to))
        output_value = max(minimum, min(maximum, output_value))
        self._output_value = self._round_to_step_size(output_value)
        self._value = 0.0 if self._to == self._from_ else (self._output_value - self._from_) / (self._to - self._from_)
        if self._value != previous_value:
            self._draw(no_color_updates=True)
        if self._variable is not None and not from_variable_callback:
            self._variable_callback_blocked = True
            self._variable.set(round(self._output_value) if isinstance(self._variable, tk.IntVar) else self._output_value)
            self._variable_callback_blocked = False

    def _variable_callback(self, *_: Any) -> None:
        if not self._variable_callback_blocked and self._variable is not None:
            self.set(self._variable.get(), from_variable_callback=True)

    def unbind(self, sequence: str | None = None, funcid: str | None = None) -> Any:
        if self._is_lifecycle_event(sequence):
            return self._unbind_lifecycle_event(sequence, funcid)
        if funcid is not None:
            raise ValueError("'funcid' must be None to preserve internal callbacks")
        result = self._canvas.unbind(sequence)
        self._create_bindings(sequence)
        return result

    def destroy(self) -> None:
        if self._variable is not None and self._variable_callback_name is not None:
            self._variable.trace_remove("write", self._variable_callback_name)
        super().destroy()


__all__ = ["Slider"]
