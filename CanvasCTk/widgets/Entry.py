from __future__ import annotations

import re
import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk
from customtkinter.windows.widgets.appearance_mode import AppearanceModeTracker

from ._shared import _appearance_color, _composite_color, _master_background_color
from .Image import Image
from .Item import Item


class Entry(Item):
    """Image-backed CTkEntry-compatible control with a flat native editor."""

    _valid_entry_attributes = {
        "exportselection", "insertborderwidth", "insertofftime", "insertontime",
        "insertwidth", "justify", "selectborderwidth", "show", "takefocus",
        "validate", "validatecommand", "xscrollcommand",
    }

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
        text_color: Any = None,
        placeholder_text_color: Any = None,
        textvariable: tk.Variable | None = None,
        placeholder_text: str | None = None,
        font: tuple | ctk.CTkFont | None = None,
        state: str = tk.NORMAL,
        *,
        input_filter: str | None = None,
        opacity: float = 1,
        canvas: tk.Canvas | None = None,
        x: int = 0,
        y: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, canvas=canvas, **kwargs)
        theme = ctk.ThemeManager.theme["CTkEntry"]
        self._width, self._height = max(1, int(width)), max(1, int(height))
        self._desired_width, self._desired_height = self._width, self._height
        self._x, self._y, self._anchor = int(x), int(y), "center"
        self._corner_radius = int(theme["corner_radius"] if corner_radius is None else corner_radius)
        self._border_width = int(theme["border_width"] if border_width is None else border_width)
        self._bg_color_transparent = bg_color == "transparent"
        self._bg_color = (
            _master_background_color(master, self.canvas)
            if self._bg_color_transparent
            else bg_color
        )
        self._fg_color = theme["fg_color"] if fg_color is None else fg_color
        self._border_color = theme["border_color"] if border_color is None else border_color
        self._text_color = theme["text_color"] if text_color is None else text_color
        self._placeholder_text_color = theme["placeholder_text_color"] if placeholder_text_color is None else placeholder_text_color
        self._track_theme_defaults(
            "CTkEntry",
            corner_radius=corner_radius is None,
            border_width=border_width is None,
            fg_color=fg_color is None,
            border_color=border_color is None,
            text_color=text_color is None,
            placeholder_text_color=placeholder_text_color is None,
        )
        self._textvariable = textvariable
        self._placeholder_text = placeholder_text
        self._placeholder_text_active = False
        self._state = str(state)
        self._font = self._coerce_font(font)
        self._opacity = float(opacity)
        self._redraw_pending = True
        self._appearance_callback_registered = False
        self.input_filter = input_filter.upper() if input_filter else None
        self._show_character = kwargs.pop("show", "")

        self._outer_background_id = self.canvas.create_rectangle(
            0, 0, 1, 1, outline="", state="hidden"
        )
        self._background = self.put(Image(
            master, canvas=self.canvas, width=self._width, height=self._height,
            x=self._x, y=self._y, anchor=self._anchor, fg_color=self._fg_color,
            border_radius=self._corner_radius, border_width=self._border_width,
            border_color=self._border_color, border_padding=0, opacity=self._opacity,
        ))
        entry_options = {key: kwargs.pop(key) for key in tuple(kwargs) if key in self._valid_entry_attributes}
        if kwargs:
            raise ValueError(f"Unsupported Entry option: {next(iter(kwargs))!r}")
        self._entry = tk.Entry(
            self.canvas,
            bd=0,
            width=1,
            highlightthickness=0,
            relief="flat",
            font=self._apply_font_scaling(self._font),
            state=self._state,
            textvariable=self._textvariable,
            show=self._show_character,
            **entry_options,
        )
        physical_x, physical_y = self._physical_point(self._x, self._y)
        self._window_id = self.canvas.create_window(
            physical_x, physical_y, window=self._entry, anchor="center", state="hidden"
        )
        self._font.add_size_configure_callback(self._font_changed)
        self._create_internal_bindings()
        self.canvas.tag_bind(
            self._outer_background_id,
            "<Button-1>",
            self._activate_editor,
            add="+",
        )
        self.canvas.tag_bind(
            self._outer_background_id,
            "<ButtonRelease-1>",
            self._finish_editor_activation,
            add="+",
        )
        self.canvas.tag_bind(
            self._background._image_id,
            "<Button-1>",
            self._activate_editor,
            add="+",
        )
        self.canvas.tag_bind(
            self._background._image_id,
            "<ButtonRelease-1>",
            self._finish_editor_activation,
            add="+",
        )
        self._context_menu = self._build_context_menu()
        if self.input_filter:
            validator = self.validate_int_like_input if self.input_filter == "INT" else self.validate_float_like_input
            self._entry.configure(validate="key", validatecommand=(self._entry.register(validator), "%P"))
        self._activate_placeholder()
        self._redraw()

    @staticmethod
    def _coerce_font(font: tuple | ctk.CTkFont | None) -> ctk.CTkFont:
        if font is None:
            return ctk.CTkFont()
        if isinstance(font, ctk.CTkFont):
            return font
        options: dict[str, Any] = {"family": font[0], "size": int(font[1])}
        if len(font) > 2:
            options["weight"] = font[2]
        if len(font) > 3:
            options["slant"] = font[3]
        return ctk.CTkFont(**options)

    @staticmethod
    def validate_float_like_input(value: str) -> bool:
        return value == "" or re.fullmatch(r"-?(\d+)?(\.\d*)?", value) is not None

    @staticmethod
    def validate_int_like_input(value: str) -> bool:
        return value == "" or re.fullmatch(r"-?\d*", value) is not None

    def _editor_color(self) -> str:
        fallback = str(self.canvas.cget("bg"))
        # bg_color is the surface directly underneath the rounded/opacity
        # layer.  When it is explicit, compositing the native editor against
        # the master's color produces a visibly different rectangle from the
        # surrounding Image-backed body.
        backdrop_source = (
            _master_background_color(self.master, self.canvas)
            if self._bg_color_transparent
            else self._bg_color
        )
        backdrop = _appearance_color(
            backdrop_source,
            fallback,
        )
        color = _appearance_color(self._fg_color, "")
        if not color or color == "transparent" or color.startswith("#00000000"):
            color = _appearance_color(self._bg_color, backdrop)
        return _composite_color(color, backdrop, self._opacity, fallback)

    def _font_changed(self) -> None:
        self._entry.configure(font=self._apply_font_scaling(self._font))
        self._redraw()

    def _set_appearance_mode(self, _: str | None = None) -> None:
        self._redraw()

    def _sync_appearance_callback(self) -> None:
        colors = (
            self._bg_color, self._fg_color, self._border_color,
            self._text_color, self._placeholder_text_color,
        )
        needed = self._is_rendered and any(isinstance(color, (tuple, list)) for color in colors)
        if needed and not self._appearance_callback_registered:
            AppearanceModeTracker.add(self._set_appearance_mode, self.canvas)
            self._appearance_callback_registered = True
        elif not needed and self._appearance_callback_registered:
            AppearanceModeTracker.remove(self._set_appearance_mode)
            self._appearance_callback_registered = False

    def _on_widget_scaling_changed(self, old_scaling: float, new_scaling: float) -> None:
        super()._on_widget_scaling_changed(old_scaling, new_scaling)
        if hasattr(self, "_entry"):
            self._redraw()

    def _create_internal_bindings(self, sequence: str | None = None) -> None:
        bindings = {
            "<FocusIn>": self._focus_in,
            "<FocusOut>": self._focus_out,
            "<ButtonRelease-1>": self._finish_editor_activation,
            "<Control-a>": self._select_all,
            "<Button-3>": self.show_context_menu,
            "<Control-z>": lambda _: self._safe_event("<<Undo>>"),
            "<Control-y>": lambda _: self._safe_event("<<Redo>>"),
        }
        for event, callback in bindings.items():
            if sequence is None or sequence == event:
                self._entry.bind(event, callback, add="+")

    def _focus_in(self, _: Any = None) -> None:
        self._deactivate_placeholder()

    def _focus_out(self, _: Any = None) -> None:
        self._activate_placeholder()

    def _activate_editor(self, _: Any = None) -> None:
        if str(self._entry.cget("state")) == tk.DISABLED:
            return None
        self._entry.focus_set()
        return None

    def _finish_editor_activation(self, _: Any = None) -> None:
        try:
            if (
                self._is_rendered
                and self._entry.winfo_exists()
                and str(self._entry.cget("state")) != tk.DISABLED
            ):
                self._entry.focus_force()
        except tk.TclError:
            pass
        return None

    def _activate_placeholder(self) -> None:
        if self._entry.get() == "" and self._placeholder_text is not None and self._textvariable in (None, ""):
            editable = self._entry.cget("state") != tk.DISABLED
            if not editable:
                self._entry.configure(state=tk.NORMAL)
            self._placeholder_text_active = True
            self._entry.configure(fg=_appearance_color(self._placeholder_text_color, "#888888"), show="")
            self._entry.insert(0, self._placeholder_text)
            if not editable:
                self._entry.configure(state=self._state)

    def _deactivate_placeholder(self) -> None:
        if not self._placeholder_text_active or self._entry.cget("state") == "readonly":
            return
        editable = self._entry.cget("state") != tk.DISABLED
        if not editable:
            self._entry.configure(state=tk.NORMAL)
        self._entry.delete(0, tk.END)
        self._entry.configure(fg=_appearance_color(self._text_color, "#ffffff"), show=self._show_character)
        self._placeholder_text_active = False
        if not editable:
            self._entry.configure(state=self._state)

    def _redraw(self) -> None:
        radius = min(max(0, self._corner_radius), self._height // 2)
        self._background.configure(
            width=self._width, height=self._height, anchor=self._anchor,
            fg_color=self._fg_color, border_radius=radius,
            border_width=self._border_width, border_color=self._border_color,
            border_padding=0, opacity=self._opacity,
        )
        if not self._is_rendered:
            # Keep the hidden Image layer's final state current without doing
            # editor/canvas layout. Image coalesces this into one raster pass
            # when geometry exposes the Entry.
            self._redraw_pending = True
            return
        self._redraw_pending = False
        editor_bg = self._editor_color()
        text_color = self._placeholder_text_color if self._placeholder_text_active else self._text_color
        self._entry.configure(
            bg=editor_bg,
            disabledbackground=editor_bg,
            readonlybackground=editor_bg,
            fg=_appearance_color(text_color, "#ffffff"),
            disabledforeground=_appearance_color(text_color, "#ffffff"),
            insertbackground=_appearance_color(self._text_color, "#ffffff"),
            font=self._apply_font_scaling(self._font),
        )
        left, top = self._winfo_origin()
        physical_left, physical_top = self._physical_point(left, top)
        physical_right, physical_bottom = self._physical_point(
            left + self._width,
            top + self._height,
        )
        self.canvas.coords(
            self._outer_background_id,
            physical_left,
            physical_top,
            physical_right,
            physical_bottom,
        )
        self.canvas.itemconfigure(
            self._outer_background_id,
            fill=_appearance_color(
                self._bg_color,
                _appearance_color(
                    _master_background_color(self.master, self.canvas),
                    str(self.canvas.cget("bg")),
                ),
            ),
            state="hidden" if self._bg_color_transparent or not self._is_rendered else "normal",
        )
        self.canvas.tag_lower(self._outer_background_id, self._background._image_id)
        x_padding = max(6, min(radius, self._height // 2))
        editor_width = max(1, self._width - x_padding * 2)
        editor_height = max(1, self._height - self._border_width * 2 - 2)
        physical_x, physical_y = self._physical_point(
            left + self._width / 2,
            top + self._height / 2,
        )
        self.canvas.coords(self._window_id, physical_x, physical_y)
        self.canvas.itemconfigure(
            self._window_id,
            width=max(1, int(round(self._apply_widget_scaling(editor_width)))),
            height=max(1, int(round(self._apply_widget_scaling(editor_height)))),
        )

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        entry_updates: dict[str, Any] = {}
        redraw = bool(require_redraw)
        for key, value in kwargs.items():
            if key == "width":
                value = max(1, int(value))
                if value != self._desired_width or value != self._width:
                    self._desired_width = self._width = value
                    redraw = True
            elif key == "height":
                value = max(1, int(value))
                if value != self._desired_height or value != self._height:
                    self._desired_height = self._height = value
                    redraw = True
            elif key == "corner_radius":
                value = int(value)
                if value != self._corner_radius: self._corner_radius, redraw = value, True
            elif key == "border_width":
                value = int(value)
                if value != self._border_width: self._border_width, redraw = value, True
            elif key == "bg_color":
                transparent = value == "transparent"
                resolved = (
                    _master_background_color(self.master, self.canvas)
                    if transparent
                    else value
                )
                if transparent != self._bg_color_transparent or resolved != self._bg_color:
                    self._bg_color_transparent = transparent
                    self._bg_color = resolved
                    redraw = True
            elif key == "fg_color":
                if value != self._fg_color: self._fg_color, redraw = value, True
            elif key == "border_color":
                if value != self._border_color: self._border_color, redraw = value, True
            elif key == "text_color":
                if value != self._text_color: self._text_color, redraw = value, True
            elif key == "placeholder_text_color":
                if value != self._placeholder_text_color: self._placeholder_text_color, redraw = value, True
            elif key == "placeholder_text":
                if value != self._placeholder_text:
                    self._placeholder_text = value
                    if self._placeholder_text_active:
                        self._deactivate_placeholder()
                    self._activate_placeholder()
                    redraw = True
            elif key == "textvariable":
                if value is not self._textvariable:
                    self._textvariable = value
                    entry_updates[key] = value
            elif key == "font":
                new_font = self._coerce_font(value)
                if new_font is not self._font:
                    self._font.remove_size_configure_callback(self._font_changed)
                    self._font = new_font
                    self._font.add_size_configure_callback(self._font_changed)
                    redraw = True
            elif key == "opacity":
                value = float(value)
                if value != self._opacity: self._opacity, redraw = value, True
            elif key == "state":
                value = str(value)
                if value != self._state:
                    self._state = value
                    entry_updates[key] = value
            elif key == "show":
                if value != self._show_character:
                    self._show_character = value
                    if not self._placeholder_text_active:
                        entry_updates[key] = value
            elif key in self._valid_entry_attributes:
                if self._entry.cget(key) != value:
                    entry_updates[key] = value
            else:
                raise ValueError(f"Unsupported Entry option: {key!r}")
        if entry_updates:
            self._entry.configure(**entry_updates)
        if redraw:
            self._redraw()
        self._sync_appearance_callback()

    config = configure

    def cget(self, attribute_name: str) -> Any:
        values = {
            "width": self._desired_width, "height": self._desired_height,
            "corner_radius": self._corner_radius, "border_width": self._border_width,
            "bg_color": self._bg_color, "fg_color": self._fg_color,
            "border_color": self._border_color, "text_color": self._text_color,
            "placeholder_text_color": self._placeholder_text_color,
            "textvariable": self._textvariable, "placeholder_text": self._placeholder_text,
            "font": self._font, "state": self._state, "show": self._show_character,
            "opacity": self._opacity,
        }
        if attribute_name in values:
            return values[attribute_name]
        if attribute_name in self._valid_entry_attributes:
            return self._entry.cget(attribute_name)
        raise ValueError(f"Unsupported Entry option: {attribute_name!r}")

    def delete(self, first_index: Any, last_index: Any = None) -> None:
        self._deactivate_placeholder()
        self._entry.delete(first_index, last_index)
        if self.canvas.focus_get() is not self._entry:
            self._activate_placeholder()

    def insert(self, index: Any, string: str) -> Any:
        self._deactivate_placeholder()
        return self._entry.insert(index, string)

    def get(self) -> str:
        return "" if self._placeholder_text_active else self._entry.get()

    def set(self, value: Any) -> None:
        self._deactivate_placeholder()
        self._entry.delete(0, tk.END)
        self._entry.insert(0, str(value))

    def _select_all(self, _: Any = None) -> str:
        self._entry.select_range(0, tk.END)
        return "break"

    def _safe_event(self, event_name: str) -> str:
        try: self._entry.event_generate(event_name)
        except tk.TclError: pass
        return "break"

    def _build_context_menu(self) -> tk.Menu:
        menu = tk.Menu(self._entry, tearoff=False)
        menu.add_command(label="Cut", command=lambda: self._entry.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: self._entry.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: self._entry.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Select All", command=self._select_all)
        return menu

    def show_context_menu(self, event: tk.Event) -> str:
        self._context_menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _set_anchor(self, anchor: str) -> None:
        self._anchor = str(anchor)
        self._background.configure(anchor=self._anchor)
        # The native editor window and the bg_color corner layer are separate
        # canvas items.  Reposition them even when grid/place changes only the
        # anchor and the resulting x/y remains unchanged (commonly row 0,
        # column 0).
        self._redraw()

    def _apply_geometry_allocation(
        self,
        width: int | None,
        height: int | None,
    ) -> None:
        target_width = self._desired_width if width is None else max(1, int(width))
        target_height = self._desired_height if height is None else max(1, int(height))
        if (target_width, target_height) == (self._width, self._height):
            return
        self._width, self._height = target_width, target_height
        self._redraw()

    def _resize_for_place(self, width: int | None, height: int | None) -> None:
        self._apply_geometry_allocation(width, height)

    def winfo_reqwidth(self) -> int:
        return max(1, int(round(self._apply_widget_scaling(self._desired_width))))

    def winfo_reqheight(self) -> int:
        return max(1, int(round(self._apply_widget_scaling(self._desired_height))))

    def move(self, x: int, y: int) -> None:
        self._x, self._y = int(x), int(y)
        self._background.move(self._x, self._y)
        self._redraw()

    def bind(self, sequence: str | None = None, command: Callable | None = None, add: str | bool = True) -> Any:
        if self._is_lifecycle_event(sequence):
            return self._bind_lifecycle_event(sequence, command, add)
        if add not in ("+", True): raise ValueError("'add' argument can only be '+' or True")
        return self._entry.bind(sequence, command, add="+")

    def unbind(self, sequence: str | None = None, funcid: str | None = None) -> None:
        if self._is_lifecycle_event(sequence):
            self._unbind_lifecycle_event(sequence, funcid)
            return
        if funcid is not None: raise ValueError("'funcid' must be None")
        self._entry.unbind(sequence)
        self._create_internal_bindings(sequence)

    def __getattr__(self, name: str) -> Any:
        entry = self.__dict__.get("_entry")
        if entry is not None and name in {
            "index", "icursor", "select_adjust", "select_from", "select_clear",
            "select_present", "select_range", "select_to", "xview", "xview_moveto",
            "xview_scroll", "event_generate", "register",
        }:
            return getattr(entry, name)
        return super().__getattr__(name)

    def focus(self) -> Any: return self._entry.focus()
    def focus_set(self) -> Any: return self._entry.focus_set()
    def focus_force(self) -> Any: return self._entry.focus_force()

    def _hide(self) -> None:
        if self._appearance_callback_registered:
            AppearanceModeTracker.remove(self._set_appearance_mode)
            self._appearance_callback_registered = False
        self.canvas.itemconfigure(self._outer_background_id, state="hidden")
        self.canvas.itemconfigure(self._window_id, state="hidden")

    def _show(self) -> None:
        self.canvas.itemconfigure(
            self._outer_background_id,
            state="hidden" if self._bg_color_transparent else "normal",
        )
        self.canvas.itemconfigure(self._window_id, state="normal")
        self._redraw()
        self._sync_appearance_callback()

    def destroy(self) -> None:
        if self._appearance_callback_registered:
            AppearanceModeTracker.remove(self._set_appearance_mode)
            self._appearance_callback_registered = False
        self._font.remove_size_configure_callback(self._font_changed)
        self._detach_layout()
        self._cleanup_canvas_element()
        self.canvas.delete(self._outer_background_id)
        self.canvas.delete(self._window_id)
        self._entry.destroy()


__all__ = ["Entry"]
