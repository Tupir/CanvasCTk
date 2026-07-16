from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Mapping
from copy import copy
from typing import Any

import customtkinter as ctk
from customtkinter.windows.widgets.core_rendering import DrawEngine
from customtkinter.windows.widgets.core_widget_classes.dropdown_menu import DropdownMenu

from ._ctk_port import CanvasCTkWidget


class OptionMenu(CanvasCTkWidget):
    """Canvas port of ``CTkOptionMenu`` with CustomTkinter's real dropdown menu."""

    def __init__(
        self,
        master: Any,
        width: int = 140,
        height: int = 28,
        corner_radius: int | None = None,
        bg_color: Any = "transparent",
        fg_color: Any = None,
        button_color: Any = None,
        button_hover_color: Any = None,
        text_color: Any = None,
        text_color_disabled: Any = None,
        dropdown_fg_color: Any = None,
        dropdown_hover_color: Any = None,
        dropdown_text_color: Any = None,
        font: tuple | ctk.CTkFont | None = None,
        dropdown_font: tuple | ctk.CTkFont | None = None,
        values: Any = None,
        variable: tk.Variable | None = None,
        state: str = tk.NORMAL,
        hover: bool = True,
        command: Callable[[Any], Any] | None = None,
        dynamic_resizing: bool = True,
        anchor: str = "w",
        *,
        canvas: tk.Canvas | None = None,
        x: int = 0,
        y: int = 0,
        **kwargs: Any,
    ) -> None:
        # A CanvasCTk widget shares its parent's canvas, so a transparent
        # background can remain genuinely transparent.  Keep this information
        # before CanvasCTkWidget resolves the CTk-compatible cget value to the
        # master's surface color.
        self._bg_color_transparent = bg_color == "transparent"
        super().__init__(master, width=width, height=height, bg_color=bg_color, canvas=canvas, x=x, y=y, **kwargs)
        # Native CTkOptionMenu paints its entire rectangular Tk canvas with
        # the resolved bg_color before drawing the rounded two-part body.  A
        # shared CanvasCTk canvas has no per-widget Tk background, so provide
        # the equivalent as the first (lowest) item in this widget's scoped
        # tag group.  This also prevents rounded-corner pixels from exposing
        # stale items when logical frames overlap or switch visibility.
        self._background_id = self._canvas.create_rectangle(
            0,
            0,
            self._current_width,
            self._current_height,
            fill="" if self._bg_color_transparent else self._apply_appearance_mode(self._bg_color),
            outline="",
            tags="widget_background",
        )
        theme = ctk.ThemeManager.theme["CTkOptionMenu"]
        dropdown_theme = ctk.ThemeManager.theme["DropdownMenu"]
        self._base_width = int(width)
        self._fg_color = self._check_color_type(theme["fg_color"] if fg_color is None else fg_color)
        self._button_color = self._check_color_type(theme["button_color"] if button_color is None else button_color)
        self._button_hover_color = self._check_color_type(
            theme["button_hover_color"] if button_hover_color is None else button_hover_color
        )
        self._corner_radius = int(theme["corner_radius"] if corner_radius is None else corner_radius)
        self._text_color = self._check_color_type(theme["text_color"] if text_color is None else text_color)
        self._text_color_disabled = self._check_color_type(
            theme["text_color_disabled"] if text_color_disabled is None else text_color_disabled
        )
        self._dropdown_fg_color = self._check_color_type(
            dropdown_theme["fg_color"] if dropdown_fg_color is None else dropdown_fg_color
        )
        self._dropdown_hover_color = self._check_color_type(
            dropdown_theme["hover_color"] if dropdown_hover_color is None else dropdown_hover_color
        )
        self._dropdown_text_color = self._check_color_type(
            dropdown_theme["text_color"] if dropdown_text_color is None else dropdown_text_color
        )
        self._track_theme_defaults(
            "CTkOptionMenu",
            corner_radius=corner_radius is None,
            fg_color=fg_color is None,
            button_color=button_color is None,
            button_hover_color=button_hover_color is None,
            text_color=text_color is None,
            text_color_disabled=text_color_disabled is None,
        )
        self._track_theme_defaults(
            "DropdownMenu",
            dropdown_fg_color="fg_color" if dropdown_fg_color is None else False,
            dropdown_hover_color="hover_color" if dropdown_hover_color is None else False,
            dropdown_text_color="text_color" if dropdown_text_color is None else False,
        )
        self._font = self._coerce_font(font)
        self._dropdown_font = self._coerce_font(dropdown_font)
        self._font.add_size_configure_callback(self._draw)
        self._value_map: Mapping[Any, str] | None = values if isinstance(values, Mapping) else None
        self._reverse_map = {str(label): key for key, label in values.items()} if self._value_map is not None else {}
        self._values = list(values) if values is not None else ["CTkOptionMenu"]
        self._current_value = self._values[0] if self._values else "CTkOptionMenu"
        self._variable = variable
        self._variable_callback_blocked = False
        self._variable_callback_name: str | None = None
        self._state = str(state)
        self._hover = bool(hover)
        self._dynamic_resizing = bool(dynamic_resizing)
        self._content_anchor = str(anchor)
        self._command = command

        self._dropdown_menu = self._create_dropdown_menu()
        self._text_id = self._canvas.create_text(0, 0, anchor="w")
        self._create_bindings()
        if self._variable is not None:
            self._variable_callback_name = self._variable.trace_add("write", self._variable_callback)
            self._current_value = self._variable.get()
        self._draw()

    def _create_dropdown_menu(self) -> Any:
        """Create the popup implementation used by this option menu.

        Kept as a factory hook so option-menu variants can provide their own
        popup without first constructing CustomTkinter's native dropdown.
        """
        return DropdownMenu(
            master=self.canvas.winfo_toplevel(),
            values=[self._display(value) for value in self._values],
            command=self._dropdown_label_callback,
            fg_color=self._dropdown_fg_color,
            hover_color=self._dropdown_hover_color,
            text_color=self._dropdown_text_color,
            font=self._dropdown_font,
        )

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

    def _display(self, value: Any) -> str:
        return str(self._value_map.get(value, value)) if self._value_map is not None else str(value)

    def _create_bindings(self, sequence: str | None = None) -> None:
        if sequence is None or sequence == "<Enter>":
            self._canvas.bind("<Enter>", self._on_enter, add="+")
        if sequence is None or sequence == "<Leave>":
            self._canvas.bind("<Leave>", self._on_leave, add="+")
        if sequence is None or sequence == "<Button-1>":
            self._canvas.bind("<Button-1>", self._clicked, add="+")

    def _draw(self, *_: Any, no_color_updates: bool = False) -> None:
        if self._dynamic_resizing:
            self._desired_width = self._current_width = self._width = max(
                self._base_width,
                self._font.measure(self._display(self._current_value)) + self._current_height + 10,
            )
        self._canvas.coords(
            self._background_id,
            0,
            0,
            self._current_width,
            self._current_height,
        )
        background = "" if self._bg_color_transparent else self._apply_appearance_mode(self._bg_color)
        self._canvas.itemconfig(self._background_id, fill=background, outline="")
        radius = min(self._corner_radius, self._current_height // 2)
        left_section_width = self._current_width - self._current_height
        requires_recoloring = self._draw_engine.draw_rounded_rect_with_border_vertical_split(
            self._current_width,
            self._current_height,
            radius,
            0,
            left_section_width,
        )
        requires_recoloring_2 = self._draw_engine.draw_dropdown_arrow(
            self._current_width - self._current_height / 2,
            self._current_height / 2,
            self._current_height / 3,
        )
        if no_color_updates and not requires_recoloring and not requires_recoloring_2:
            return

        left_fill = self._apply_appearance_mode(self._fg_color)
        right_fill = self._apply_appearance_mode(self._button_color)
        self._canvas.itemconfig("inner_parts_left", fill=left_fill, outline=left_fill)
        self._canvas.itemconfig("inner_parts_right", fill=right_fill, outline=right_fill)
        text_color = self._text_color_disabled if self._state == tk.DISABLED else self._text_color
        arrow_color = self._apply_appearance_mode(text_color)
        self._canvas.itemconfig("dropdown_arrow", fill=arrow_color)

        padding = max(radius, 3)
        if self._content_anchor in ("center", "n", "s"):
            x = left_section_width / 2
            text_anchor = "center"
        elif self._content_anchor in ("e", "ne", "se"):
            x = left_section_width - padding
            text_anchor = "e"
        else:
            x = padding
            text_anchor = "w"
        self._canvas.coords(self._text_id, x, self._current_height / 2)
        self._canvas.itemconfig(
            self._text_id,
            text=self._display(self._current_value),
            anchor=text_anchor,
            font=self._font,
            fill=arrow_color,
        )
        self.canvas.tag_raise(self._text_id)

    def _set_dimensions(self, width: int | None = None, height: int | None = None) -> bool:
        base_changed = width is not None and int(width) != self._base_width
        if width is not None:
            self._base_width = int(width)
        dimensions_changed = super()._set_dimensions(width, height)
        if base_changed and not dimensions_changed:
            self._draw()
        return dimensions_changed or base_changed

    def _on_enter(self, _: Any = None) -> None:
        if self._hover and self._state != tk.DISABLED and self._values:
            color = self._apply_appearance_mode(self._button_hover_color)
            self._canvas.itemconfig("inner_parts_right", fill=color, outline=color)
            self.canvas.configure(cursor="hand2")

    def _on_leave(self, _: Any = None) -> None:
        color = self._apply_appearance_mode(self._button_color)
        self._canvas.itemconfig("inner_parts_right", fill=color, outline=color)
        self.canvas.configure(cursor="")

    def _clicked(self, _event: Any = None) -> None:
        if self._state != tk.DISABLED and self._values:
            self._open_dropdown_menu()

    def _open_dropdown_menu(self) -> None:
        self._dropdown_menu.open(
            self.winfo_rootx(),
            self.winfo_rooty() + self._apply_widget_scaling(self._current_height),
        )

    def _dropdown_label_callback(self, label: str) -> None:
        self._dropdown_callback(self._reverse_map.get(label, label))

    def _dropdown_callback(self, value: Any) -> None:
        self.set(value)
        if self._command is not None:
            self._command(value)

    def _variable_callback(self, *_: Any) -> None:
        if not self._variable_callback_blocked and self._variable is not None:
            self._current_value = self._variable.get()
            self._draw()

    def set(self, value: Any) -> None:
        self._current_value = value
        self._draw()
        if self._variable is not None:
            self._variable_callback_blocked = True
            self._variable.set(value)
            self._variable_callback_blocked = False

    def get(self) -> Any:
        return self._current_value

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        if "bg_color" in kwargs:
            self._bg_color_transparent = kwargs["bg_color"] == "transparent"
        if "corner_radius" in kwargs:
            self._corner_radius = int(kwargs.pop("corner_radius"))
            require_redraw = True
        for name in ("fg_color", "button_color", "button_hover_color", "text_color", "text_color_disabled"):
            if name in kwargs:
                setattr(self, f"_{name}", self._check_color_type(kwargs.pop(name)))
                require_redraw = True
        dropdown_updates: dict[str, Any] = {}
        for name, dropdown_name in (
            ("dropdown_fg_color", "fg_color"),
            ("dropdown_hover_color", "hover_color"),
            ("dropdown_text_color", "text_color"),
        ):
            if name in kwargs:
                value = self._check_color_type(kwargs.pop(name))
                setattr(self, f"_{name}", value)
                dropdown_updates[dropdown_name] = value
        if "font" in kwargs:
            self._font.remove_size_configure_callback(self._draw)
            self._font = self._coerce_font(kwargs.pop("font"))
            self._font.add_size_configure_callback(self._draw)
            require_redraw = True
        if "dropdown_font" in kwargs:
            self._dropdown_font = self._coerce_font(kwargs.pop("dropdown_font"))
            dropdown_updates["font"] = self._dropdown_font
        if "values" in kwargs:
            values = kwargs.pop("values")
            self._value_map = values if isinstance(values, Mapping) else None
            self._reverse_map = {str(label): key for key, label in values.items()} if self._value_map is not None else {}
            self._values = list(values)
            dropdown_updates["values"] = [self._display(value) for value in self._values]
            require_redraw = True
        if "variable" in kwargs:
            if self._variable is not None and self._variable_callback_name is not None:
                self._variable.trace_remove("write", self._variable_callback_name)
            self._variable = kwargs.pop("variable")
            self._variable_callback_name = None
            if self._variable is not None and self._variable != "":
                self._variable_callback_name = self._variable.trace_add("write", self._variable_callback)
                self._current_value = self._variable.get()
            else:
                self._variable = None
            require_redraw = True
        if "state" in kwargs:
            self._state = str(kwargs.pop("state"))
            require_redraw = True
        if "hover" in kwargs:
            self._hover = bool(kwargs.pop("hover"))
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if "dynamic_resizing" in kwargs:
            self._dynamic_resizing = bool(kwargs.pop("dynamic_resizing"))
            require_redraw = True
        if "anchor" in kwargs:
            self._content_anchor = str(kwargs.pop("anchor"))
            require_redraw = True
        if dropdown_updates:
            self._dropdown_menu.configure(**dropdown_updates)
        super().configure(require_redraw=require_redraw, **kwargs)

    config = configure

    def cget(self, attribute_name: str) -> Any:
        values = {
            "corner_radius": self._corner_radius,
            "fg_color": self._fg_color,
            "button_color": self._button_color,
            "button_hover_color": self._button_hover_color,
            "text_color": self._text_color,
            "text_color_disabled": self._text_color_disabled,
            "dropdown_fg_color": self._dropdown_fg_color,
            "dropdown_hover_color": self._dropdown_hover_color,
            "dropdown_text_color": self._dropdown_text_color,
            "font": self._font,
            "dropdown_font": self._dropdown_font,
            "values": copy(self._values),
            "variable": self._variable,
            "state": self._state,
            "hover": self._hover,
            "command": self._command,
            "dynamic_resizing": self._dynamic_resizing,
            "anchor": self._content_anchor,
        }
        return values[attribute_name] if attribute_name in values else super().cget(attribute_name)

    def destroy(self) -> None:
        self._font.remove_size_configure_callback(self._draw)
        if self._variable is not None and self._variable_callback_name is not None:
            self._variable.trace_remove("write", self._variable_callback_name)
        self._dropdown_menu.destroy()
        super().destroy()


__all__ = ["OptionMenu"]
