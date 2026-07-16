from __future__ import annotations

import tkinter as tk
from typing import Any

import customtkinter as ctk

from .Entry import Entry
from .OptionMenu import OptionMenu


class ComboBox(OptionMenu):
    def __init__(
        self,
        master: Any,
        width: int = 140,
        height: int = 28,
        corner_radius: int | None = None,
        border_width: int | None = None,
        bg_color: Any = "transparent",
        fg_color: Any = None,
        border_color: Any = None,
        button_color: Any = None,
        button_hover_color: Any = None,
        dropdown_fg_color: Any = None,
        dropdown_hover_color: Any = None,
        dropdown_text_color: Any = None,
        text_color: Any = None,
        text_color_disabled: Any = None,
        font: tuple | ctk.CTkFont | None = None,
        dropdown_font: tuple | ctk.CTkFont | None = None,
        values: list[str] | None = None,
        state: str = "normal",
        hover: bool = True,
        variable: tk.Variable | None = None,
        command: Any = None,
        justify: str = "left",
        *,
        canvas: tk.Canvas | None = None,
        x: int = 0,
        y: int = 0,
        **kwargs: Any,
    ) -> None:
        theme = ctk.ThemeManager.theme["CTkComboBox"]
        theme_defaults = {
            "corner_radius": corner_radius is None,
            "fg_color": fg_color is None,
            "button_color": button_color is None,
            "button_hover_color": button_hover_color is None,
            "text_color": text_color is None,
            "text_color_disabled": text_color_disabled is None,
            "border_width": border_width is None,
            "border_color": border_color is None,
        }
        corner_radius = theme["corner_radius"] if corner_radius is None else corner_radius
        fg_color = theme["fg_color"] if fg_color is None else fg_color
        button_color = theme["button_color"] if button_color is None else button_color
        button_hover_color = theme["button_hover_color"] if button_hover_color is None else button_hover_color
        text_color = theme["text_color"] if text_color is None else text_color
        text_color_disabled = theme["text_color_disabled"] if text_color_disabled is None else text_color_disabled
        if values is None:
            values = ["CTkComboBox"]
        self._combo_variable = variable
        self._combo_border_width = int(theme["border_width"] if border_width is None else border_width)
        self._combo_border_color = theme["border_color"] if border_color is None else border_color
        super().__init__(
            master,
            width=width,
            height=height,
            corner_radius=corner_radius,
            bg_color=bg_color,
            fg_color=fg_color,
            button_color=button_color,
            button_hover_color=button_hover_color,
            text_color=text_color,
            text_color_disabled=text_color_disabled,
            dropdown_fg_color=dropdown_fg_color,
            dropdown_hover_color=dropdown_hover_color,
            dropdown_text_color=dropdown_text_color,
            font=font,
            dropdown_font=dropdown_font,
            values=values,
            variable=None,
            state=state,
            hover=hover,
            command=command,
            dynamic_resizing=False,
            canvas=canvas,
            x=x,
            y=y,
            **kwargs,
        )
        self._track_theme_defaults("CTkComboBox", **theme_defaults)
        initial = (
            variable.get()
            if variable not in (None, "") and variable.get() != ""
            else self._display(self._current_value)
        )
        self._entry = self.put(Entry(
            master, canvas=self.canvas, width=max(1, self._width - 30), height=self._height,
            corner_radius=self._corner_radius, border_width=self._combo_border_width,
            border_color=self._combo_border_color, fg_color=self._fg_color,
            text_color=self._text_color, font=self._font, textvariable=variable,
            justify=justify, state=state,
        ))
        self._entry.set(initial)
        self._canvas.itemconfig(self._text_id, state="hidden")
        self._layout_entry()

    def _layout_entry(self) -> None:
        left, top = self._winfo_origin()
        width = max(1, self._width - 30)
        self._entry._apply_geometry_allocation(width, self._height)
        self._entry.move(round(left + width / 2), round(top + self._height / 2))
        self._canvas.itemconfig(self._text_id, state="hidden")

    def set(self, value: Any) -> None:
        self._current_value = value
        if hasattr(self, "_entry"):
            if self._state == "readonly":
                self._entry.configure(state=tk.NORMAL)
                self._entry.set(self._display(value))
                self._entry.configure(state="readonly")
            else:
                self._entry.set(self._display(value))
        self._draw()

    def get(self) -> Any:
        if not hasattr(self, "_entry"):
            return self._current_value
        value = self._entry.get()
        return self._reverse_map.get(value, value)

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        justify = kwargs.pop("justify", None)
        variable = kwargs.pop("variable", None) if "variable" in kwargs else self._combo_variable
        entry_state = kwargs.get("state")
        entry_corner_radius = kwargs.get("corner_radius")
        if "border_width" in kwargs: self._combo_border_width = int(kwargs.pop("border_width"))
        if "border_color" in kwargs: self._combo_border_color = kwargs.pop("border_color")
        super().configure(require_redraw=require_redraw, **kwargs)
        if hasattr(self, "_entry"):
            updates: dict[str, Any] = {"border_width": self._combo_border_width,
                                       "border_color": self._combo_border_color,
                                       "fg_color": self._fg_color, "text_color": self._text_color,
                                       "font": self._font}
            if justify is not None: updates["justify"] = justify
            if entry_state is not None: updates["state"] = entry_state
            if entry_corner_radius is not None: updates["corner_radius"] = entry_corner_radius
            if variable is not self._combo_variable:
                self._combo_variable = variable; updates["textvariable"] = variable
            self._entry.configure(**updates)
            self._layout_entry()

    config = configure

    def cget(self, name: str) -> Any:
        if name == "border_width": return self._combo_border_width
        if name == "border_color": return self._combo_border_color
        if name == "variable": return self._combo_variable
        if name == "justify": return self._entry.cget("justify")
        return super().cget(name)

    def bind(self, sequence: str | None = None, command: Any = None, add: Any = True) -> Any:
        if self._is_lifecycle_event(sequence):
            return self._bind_lifecycle_event(sequence, command, add)
        result = super().bind(sequence, command, add)
        entry_result = self._entry.bind(sequence, command, add)
        return entry_result or result

    def unbind(self, sequence: str | None = None, funcid: str | None = None) -> None:
        if self._is_lifecycle_event(sequence):
            self._unbind_lifecycle_event(sequence, funcid)
            return
        super().unbind(sequence, funcid)
        self._entry.unbind(sequence, funcid)

    def move(self, x: int, y: int) -> None:
        super().move(x, y)
        if hasattr(self, "_entry"): self._layout_entry()

    def _draw(self, *args: Any, **kwargs: Any) -> None:
        super()._draw(*args, **kwargs)
        if hasattr(self, "_entry"):
            self._canvas.itemconfig(self._text_id, state="hidden")
            self._layout_entry()

    def _show(self) -> None:
        super()._show()
        self._canvas.itemconfig(self._text_id, state="hidden")
        self._entry.show()


__all__ = ["ComboBox"]
