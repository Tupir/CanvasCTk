from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ._ctk_port import CanvasCTkWidget


class RadioButton(CanvasCTkWidget):
    """Canvas port of CustomTkinter's ``CTkRadioButton`` draw/state model."""

    def __init__(
        self,
        master: Any,
        width: int = 100,
        height: int = 22,
        radiobutton_width: int = 22,
        radiobutton_height: int = 22,
        corner_radius: int | None = None,
        border_width_unchecked: int | None = None,
        border_width_checked: int | None = None,
        bg_color: Any = "transparent",
        fg_color: Any = None,
        hover_color: Any = None,
        border_color: Any = None,
        text_color: Any = None,
        text_color_disabled: Any = None,
        text: str = "CTkRadioButton",
        font: tuple | ctk.CTkFont | None = None,
        textvariable: tk.Variable | None = None,
        variable: tk.Variable | None = None,
        value: Any = 0,
        state: str = tk.NORMAL,
        hover: bool = True,
        command: Callable[[], Any] | None = None,
        *,
        canvas: tk.Canvas | None = None,
        x: int = 0,
        y: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, width=width, height=height, bg_color=bg_color, canvas=canvas, x=x, y=y, **kwargs)
        theme = ctk.ThemeManager.theme["CTkRadioButton"]

        self._radiobutton_width = int(radiobutton_width)
        self._radiobutton_height = int(radiobutton_height)
        self._fg_color = self._check_color_type(theme["fg_color"] if fg_color is None else fg_color)
        self._hover_color = self._check_color_type(theme["hover_color"] if hover_color is None else hover_color)
        self._border_color = self._check_color_type(theme["border_color"] if border_color is None else border_color)
        self._corner_radius = int(theme["corner_radius"] if corner_radius is None else corner_radius)
        self._border_width_unchecked = int(theme["border_width_unchecked"] if border_width_unchecked is None else border_width_unchecked)
        self._border_width_checked = int(theme["border_width_checked"] if border_width_checked is None else border_width_checked)
        self._text = "" if text is None else str(text)
        self._text_color = self._check_color_type(theme["text_color"] if text_color is None else text_color)
        self._text_color_disabled = self._check_color_type(
            theme["text_color_disabled"] if text_color_disabled is None else text_color_disabled
        )
        self._track_theme_defaults(
            "CTkRadioButton",
            fg_color=fg_color is None,
            hover_color=hover_color is None,
            border_color=border_color is None,
            corner_radius=corner_radius is None,
            border_width_unchecked=border_width_unchecked is None,
            border_width_checked=border_width_checked is None,
            text_color=text_color is None,
            text_color_disabled=text_color_disabled is None,
        )
        self._font = self._coerce_font(font)
        self._textvariable = textvariable
        self._command = command
        self._state = str(state)
        self._hover = bool(hover)
        self._hovered = False
        self._check_state = False
        self._value = value
        self._variable = variable
        self._variable_callback_blocked = False
        self._variable_callback_name: str | None = None

        self._text_id = self._canvas.create_text(0, 0, anchor="w", text=self._text, font=self._font)
        self._font.add_size_configure_callback(self._refresh_text)
        if self._textvariable is not None:
            self.trace_write(self._textvariable, self._textvariable_callback)
        if self._variable is not None:
            self._variable_callback_name = self._variable.trace_add("write", self._variable_callback)
            self._check_state = self._variable.get() == self._value

        self._create_bindings()
        self._draw()

    @staticmethod
    def _coerce_font(font: tuple | ctk.CTkFont | None) -> ctk.CTkFont:
        if isinstance(font, ctk.CTkFont):
            return font
        if font is None:
            return ctk.CTkFont()
        options: dict[str, Any] = {"family": font[0], "size": int(font[1])}
        if len(font) > 2:
            options["weight"] = font[2]
        return ctk.CTkFont(**options)

    def _background_fill(self) -> str:
        if self._bg_color != "transparent":
            return str(self._apply_appearance_mode(self._bg_color))
        parent = self.master
        while parent is not None:
            try:
                color = parent.cget("fg_color")
                if color not in (None, "transparent"):
                    return str(self._apply_appearance_mode(color))
            except Exception:
                pass
            parent = getattr(parent, "master", None)
        return str(self.canvas.cget("bg"))

    def _create_bindings(self, sequence: str | None = None) -> None:
        if sequence is None or sequence == "<Enter>":
            self._canvas.bind("<Enter>", self._on_enter, add="+")
        if sequence is None or sequence == "<Leave>":
            self._canvas.bind("<Leave>", self._on_leave, add="+")
        if sequence is None or sequence == "<Button-1>":
            self._canvas.bind("<Button-1>", self.invoke, add="+")

    def _draw(self, *_: Any, no_color_updates: bool = False) -> None:
        border_width = self._border_width_checked if self._check_state else self._border_width_unchecked
        requires_recoloring = self._draw_engine.draw_rounded_rect_with_border(
            self._radiobutton_width,
            self._radiobutton_height,
            self._corner_radius,
            border_width,
        )
        if no_color_updates and not requires_recoloring:
            return

        self._refresh_control_colors()
        self._refresh_text()

    def _refresh_control_colors(self) -> None:
        background = self._background_fill()
        border = self._hover_color if self._hovered and self._state == tk.NORMAL else (
            self._fg_color if self._check_state else self._border_color
        )
        border = self._apply_appearance_mode(border)
        self._canvas.itemconfig("border_parts", fill=border, outline=border)
        self._canvas.itemconfig("inner_parts", fill=background, outline=background)

    def _refresh_text(self) -> None:
        text_color = self._text_color_disabled if self._state == tk.DISABLED else self._text_color
        left = self._radiobutton_width + 6
        self._canvas.coords(self._text_id, left, self._current_height / 2)
        self._canvas.itemconfig(
            self._text_id,
            text=self._text,
            font=self._font,
            fill=self._apply_appearance_mode(text_color),
            state="normal",
        )

    def _set_dimensions(self, width: int | None = None, height: int | None = None) -> bool:
        return super()._set_dimensions(width, height)

    def _textvariable_callback(self, _: Any, value: Any) -> None:
        self._text = "" if value is None else str(value)
        self._refresh_text()

    def _variable_callback(self, *_: Any) -> None:
        if not self._variable_callback_blocked and self._variable is not None:
            checked = self._variable.get() == self._value
            if checked != self._check_state:
                self._check_state = checked
                self._draw()

    def _on_enter(self, _: Any = None) -> None:
        if self._hover and self._state == tk.NORMAL and not self._hovered:
            self._hovered = True
            self.canvas.configure(cursor="hand2")
            self._refresh_control_colors()

    def _on_leave(self, _: Any = None) -> None:
        if not self._hovered:
            return
        self._hovered = False
        self.canvas.configure(cursor="")
        self._refresh_control_colors()

    def invoke(self, _event: Any = None) -> None:
        if self._state != tk.NORMAL:
            return
        if not self._check_state:
            self.select()
        if self._command is not None:
            self._command()

    def select(self, from_variable_callback: bool = False) -> None:
        if not self._check_state:
            self._check_state = True
            self._draw()
        if self._variable is not None and not from_variable_callback:
            self._variable_callback_blocked = True
            self._variable.set(self._value)
            self._variable_callback_blocked = False

    def deselect(self, from_variable_callback: bool = False) -> None:
        if self._check_state:
            self._check_state = False
            self._draw()
        if self._variable is not None and not from_variable_callback:
            self._variable_callback_blocked = True
            self._variable.set("")
            self._variable_callback_blocked = False

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        refresh_control = False
        refresh_text = False
        for name in ("corner_radius", "border_width_unchecked", "border_width_checked", "radiobutton_width", "radiobutton_height"):
            if name in kwargs:
                setattr(self, f"_{name}", int(kwargs.pop(name)))
                require_redraw = True
        for name in ("fg_color", "hover_color", "border_color", "text_color", "text_color_disabled"):
            if name in kwargs:
                setattr(self, f"_{name}", self._check_color_type(kwargs.pop(name)))
                if name in {"text_color", "text_color_disabled"}:
                    refresh_text = True
                else:
                    refresh_control = True
        if "text" in kwargs:
            text = kwargs.pop("text")
            self._text = "" if text is None else str(text)
            refresh_text = True
        if "font" in kwargs:
            self._font.remove_size_configure_callback(self._refresh_text)
            self._font = self._coerce_font(kwargs.pop("font"))
            self._font.add_size_configure_callback(self._refresh_text)
            refresh_text = True
        if "textvariable" in kwargs:
            self._textvariable = kwargs.pop("textvariable")
            if self._textvariable is not None:
                self.trace_write(self._textvariable, self._textvariable_callback)
            refresh_text = True
        if "variable" in kwargs:
            if self._variable is not None and self._variable_callback_name is not None:
                self._variable.trace_remove("write", self._variable_callback_name)
            self._variable = kwargs.pop("variable")
            self._variable_callback_name = None
            if self._variable is not None and self._variable != "":
                self._variable_callback_name = self._variable.trace_add("write", self._variable_callback)
                checked = self._variable.get() == self._value
                if checked != self._check_state:
                    self._check_state = checked
                    require_redraw = True
        if "value" in kwargs:
            self._value = kwargs.pop("value")
            checked = bool(self._variable is not None and self._variable != "" and self._variable.get() == self._value)
            if checked != self._check_state:
                self._check_state = checked
                require_redraw = True
        if "state" in kwargs:
            self._state = str(kwargs.pop("state"))
            refresh_control = refresh_text = True
        if "hover" in kwargs:
            self._hover = bool(kwargs.pop("hover"))
            if not self._hover and self._hovered:
                self._hovered = False
                refresh_control = True
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        super().configure(require_redraw=require_redraw, **kwargs)
        if not require_redraw:
            if refresh_control:
                self._refresh_control_colors()
            if refresh_text:
                self._refresh_text()

    config = configure

    def cget(self, attribute_name: str) -> Any:
        values = {
            "corner_radius": self._corner_radius,
            "border_width_unchecked": self._border_width_unchecked,
            "border_width_checked": self._border_width_checked,
            "radiobutton_width": self._radiobutton_width,
            "radiobutton_height": self._radiobutton_height,
            "fg_color": self._fg_color,
            "hover_color": self._hover_color,
            "border_color": self._border_color,
            "text_color": self._text_color,
            "text_color_disabled": self._text_color_disabled,
            "text": self._text,
            "font": self._font,
            "textvariable": self._textvariable,
            "variable": self._variable,
            "value": self._value,
            "state": self._state,
            "hover": self._hover,
            "command": self._command,
        }
        return values[attribute_name] if attribute_name in values else super().cget(attribute_name)

    def destroy(self) -> None:
        self._font.remove_size_configure_callback(self._refresh_text)
        if self._variable is not None and self._variable_callback_name is not None:
            self._variable.trace_remove("write", self._variable_callback_name)
        super().destroy()


__all__ = ["RadioButton"]
