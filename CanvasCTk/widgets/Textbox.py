from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter as ctk
from customtkinter.windows.widgets.appearance_mode import AppearanceModeTracker

from ._shared import _appearance_color, _composite_color, _master_background_color
from .Image import Image
from .Item import Item
from .Label import Label


class Textbox(Item):
    """Image-backed counterpart of ``customtkinter.CTkTextbox``."""

    _valid_text_attributes = {
        "autoseparators", "cursor", "exportselection", "insertborderwidth",
        "insertofftime", "insertontime", "insertwidth", "maxundo", "padx", "pady",
        "selectborderwidth", "spacing1", "spacing2", "spacing3", "state", "tabs",
        "takefocus", "undo", "wrap", "xscrollcommand", "yscrollcommand",
    }

    def __init__(
        self,
        master: Any,
        width: int = 200,
        height: int = 200,
        corner_radius: int | None = None,
        border_width: int | None = None,
        border_spacing: int = 3,
        bg_color: Any = "transparent",
        fg_color: Any = None,
        border_color: Any = None,
        text_color: Any = None,
        scrollbar_button_color: Any = None,
        scrollbar_button_hover_color: Any = None,
        font: tuple | ctk.CTkFont | None = None,
        activate_scrollbars: bool = True,
        *,
        text_variable: tk.Variable | None = None,
        opacity: float = 1,
        canvas: tk.Canvas | None = None,
        x: int = 0,
        y: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, canvas=canvas, **kwargs)
        theme = ctk.ThemeManager.theme["CTkTextbox"]
        self._width, self._height = max(1, int(width)), max(1, int(height))
        self._desired_width, self._desired_height = self._width, self._height
        self._x, self._y, self._anchor = int(x), int(y), "center"
        self._corner_radius = int(theme["corner_radius"] if corner_radius is None else corner_radius)
        self._border_width = int(theme["border_width"] if border_width is None else border_width)
        self._border_spacing = int(border_spacing)
        self._bg_color = _master_background_color(master, self.canvas) if bg_color == "transparent" else bg_color
        self._fg_color = theme["fg_color"] if fg_color is None else fg_color
        self._border_color = theme["border_color"] if border_color is None else border_color
        self._text_color = theme["text_color"] if text_color is None else text_color
        self._scrollbar_button_color = theme["scrollbar_button_color"] if scrollbar_button_color is None else scrollbar_button_color
        self._scrollbar_button_hover_color = theme["scrollbar_button_hover_color"] if scrollbar_button_hover_color is None else scrollbar_button_hover_color
        self._track_theme_defaults(
            "CTkTextbox",
            corner_radius=corner_radius is None,
            border_width=border_width is None,
            fg_color=fg_color is None,
            border_color=border_color is None,
            text_color=text_color is None,
            scrollbar_button_color=scrollbar_button_color is None,
            scrollbar_button_hover_color=scrollbar_button_hover_color is None,
        )
        self._font = self._coerce_font(font)
        self._opacity = float(opacity)
        self._scrollbars_activated = bool(activate_scrollbars)
        self.text_variable = text_variable
        self._syncing = False
        self._redraw_pending = True
        self._scrollbar_refresh_pending = False
        self._content_layout_pending = False
        self._appearance_callback_registered = False
        self._external_xscrollcommand = kwargs.pop("xscrollcommand", None)
        self._external_yscrollcommand = kwargs.pop("yscrollcommand", None)

        self._background = self.put(Image(
            master, canvas=self.canvas, width=self._width, height=self._height,
            x=self._x, y=self._y, anchor=self._anchor, fg_color=self._fg_color,
            border_radius=self._corner_radius, border_width=self._border_width,
            border_color=self._border_color, border_padding=0, opacity=self._opacity,
        ))
        text_options = {key: kwargs.pop(key) for key in tuple(kwargs) if key in self._valid_text_attributes}
        if kwargs:
            raise ValueError(f"Unsupported Textbox option: {next(iter(kwargs))!r}")
        self._textbox = tk.Text(
            self.canvas, width=0, height=0, bd=0, highlightthickness=0,
            relief="flat", font=self._apply_font_scaling(self._font), **text_options,
        )
        self._editor_active = False
        physical_x, physical_y = self._physical_point(self._x, self._y)
        self._window_id = self.canvas.create_window(
            physical_x, physical_y, window=self._textbox, anchor="center", state="hidden"
        )

        # Imported lazily to avoid the containers -> widgets import cycle.
        from ..containers import ScrollableFrame

        self._text_scroller = self.put(ScrollableFrame(
            self,
            canvas=self.canvas,
            width=max(1, self._width - 16),
            height=self._height,
            corner_radius=0,
            border_width=0,
            bg_color="transparent",
            fg_color="transparent",
            orientation="vertical",
            hide_scrollbar=not self._scrollbars_activated,
            scrollbar_fg_color="transparent",
            scrollbar_button_color=self._scrollbar_button_color,
            scrollbar_button_hover_color=self._scrollbar_button_hover_color,
            opacity=0,
        ))
        self._text_scroller.hide()
        self._text_scroller._scrollbar.configure(command=self._scroll_rendered_text)
        self._display_lines: list[Label] = []
        self._textbox.configure(xscrollcommand=self._on_xscroll, yscrollcommand=self._on_yscroll)
        self._font.add_size_configure_callback(self._font_changed)
        self._context_menu = self._build_context_menu()
        self._textbox.bind("<Button-3>", self.show_context_menu)
        self._textbox.bind("<KeyRelease>", self._widget_changed, add="+")
        self._textbox.bind("<FocusIn>", self._editor_focus_in, add="+")
        self._textbox.bind("<FocusOut>", self._editor_focus_out, add="+")
        self.canvas.tag_bind(self._background._image_id, "<Button-1>", self._activate_editor, add="+")
        self._create_scroll_bindings()
        if text_variable is not None:
            self.set(text_variable.get())
            self.trace_write(text_variable, self._variable_changed)
        self._redraw()
        self._schedule_scrollbar_refresh()

    @staticmethod
    def _coerce_font(font: tuple | ctk.CTkFont | None) -> ctk.CTkFont:
        if isinstance(font, ctk.CTkFont): return font
        if font is None: return ctk.CTkFont()
        options: dict[str, Any] = {"family": font[0], "size": int(font[1])}
        if len(font) > 2: options["weight"] = font[2]
        return ctk.CTkFont(**options)

    def _surface_color(self) -> str:
        fallback = str(self.canvas.cget("bg"))
        backdrop = _appearance_color(
            _master_background_color(self.master, self.canvas),
            fallback,
        )
        color = _appearance_color(self._fg_color, "")
        if not color or color == "transparent" or color == "#00000000":
            color = _appearance_color(self._bg_color, backdrop)
        return _composite_color(color, backdrop, self._opacity, fallback)

    def _font_changed(self) -> None:
        self._textbox.configure(font=self._apply_font_scaling(self._font))
        self._redraw()

    def _set_appearance_mode(self, _: str | None = None) -> None:
        self._redraw()

    def _sync_appearance_callback(self) -> None:
        colors = (
            self._bg_color, self._fg_color, self._border_color,
            self._text_color, self._scrollbar_button_color,
            self._scrollbar_button_hover_color,
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
        if hasattr(self, "_textbox"):
            self._redraw()

    def _variable_changed(self, _: Any, value: Any) -> None:
        if not self._syncing and self.get("1.0", "end-1c") != str(value):
            self.set(value)

    def _widget_changed(self, _: Any = None) -> None:
        if self.text_variable is not None:
            self._syncing = True
            self.text_variable.set(self.get("1.0", "end-1c"))
            self._syncing = False
        self._sync_canvas_text()
        self._schedule_scrollbar_refresh()

    def _editor_focus_in(self, _: Any = None) -> None:
        self._editor_active = True
        self._sync_canvas_text()

    def _editor_focus_out(self, _: Any = None) -> None:
        self._editor_active = False
        self._sync_canvas_text()
        first = getattr(self, "_native_y_fraction", (0.0, 1.0))[0]
        self.after_idle(lambda: self._text_scroller.scroll_to(first))

    def _activate_editor(self, _: Any = None) -> str | None:
        if str(self._textbox.cget("state")) == tk.DISABLED:
            return "break"
        self._textbox.yview_moveto(self._text_scroller._scrollbar.get()[0])
        self._editor_active = True
        self._sync_canvas_text()
        self._textbox.focus_set()
        return "break"

    def _create_scroll_bindings(self) -> None:
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self._textbox.bind(sequence, self._mouse_scroll_event, add="+")
        registry = getattr(self.canvas, "_canvasctk_textbox_wheel_registry", None)
        if registry is None:
            registry = []
            self.canvas._canvasctk_textbox_wheel_registry = registry
            bindtag = f"CanvasCTkTextboxWheel{id(self.canvas)}"
            self.canvas._canvasctk_textbox_wheel_bindtag = bindtag

            def dispatch(event: Any) -> str | None:
                for textbox in reversed(tuple(registry)):
                    if textbox._wheel_event_inside(event):
                        return textbox._mouse_scroll_event(event)
                return None

            self.canvas._canvasctk_textbox_wheel_dispatcher = dispatch
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.canvas.bind_class(bindtag, sequence, dispatch)
            bindtags = list(self.canvas.bindtags())
            if bindtag not in bindtags:
                bindtags.insert(0, bindtag)
                self.canvas.bindtags(tuple(bindtags))
        if self not in registry:
            registry.append(self)

    def _remove_scroll_bindings(self) -> None:
        registry = getattr(self.canvas, "_canvasctk_textbox_wheel_registry", None)
        if registry is None:
            return
        if self in registry:
            registry.remove(self)
        if registry:
            return
        bindtag = getattr(self.canvas, "_canvasctk_textbox_wheel_bindtag", None)
        if bindtag is not None:
            try:
                self.canvas.bindtags(
                    tuple(tag for tag in self.canvas.bindtags() if tag != bindtag)
                )
                for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                    self.canvas.unbind_class(bindtag, sequence)
            except tk.TclError:
                pass
        self.canvas._canvasctk_textbox_wheel_registry = None
        self.canvas._canvasctk_textbox_wheel_bindtag = None
        self.canvas._canvasctk_textbox_wheel_dispatcher = None

    def _wheel_event_inside(self, event: Any) -> bool:
        if self._destroyed or not self._is_rendered or self.is_hidden:
            return False
        try:
            pointer_x = int(getattr(event, "x_root", self.canvas.winfo_pointerx()))
            pointer_y = int(getattr(event, "y_root", self.canvas.winfo_pointery()))
            left = self.winfo_rootx()
            top = self.winfo_rooty()
            return (
                left <= pointer_x < left + self.winfo_width()
                and top <= pointer_y < top + self.winfo_height()
            )
        except tk.TclError:
            return False

    @staticmethod
    def _scroll_units(event: Any) -> int:
        button = getattr(event, "num", None)
        if button == 4:
            return -1
        if button == 5:
            return 1
        delta = int(getattr(event, "delta", 0) or 0)
        if delta == 0:
            return 0
        if abs(delta) >= 120:
            units = -int(delta / 120)
            if units:
                return units
        return -1 if delta > 0 else 1

    def _mouse_scroll_event(self, event: Any) -> str:
        units = self._scroll_units(event)
        if units == 0:
            return "break"
        canvas_mode = self._canvas_text_enabled()
        try:
            if canvas_mode:
                self._scroll_rendered_text("scroll", units, "units")
            else:
                self._textbox.yview_scroll(units, "units")
                self._editor_active = True
                self._sync_canvas_text()
                self._textbox.focus_set()
        except tk.TclError:
            pass
        if not canvas_mode:
            self._schedule_scrollbar_refresh()
        return "break"

    def _canvas_text_enabled(self) -> bool:
        return not self._editor_active

    def _ensure_display_lines(self, count: int) -> None:
        wraplength = max(1, getattr(self, "_display_text_width", self._width) - 4)
        while len(self._display_lines) < count:
            label = Label(
                self._text_scroller,
                width=wraplength,
                height=1,
                text="",
                fg_color="transparent",
                text_color=self._text_color,
                font=self._font,
                anchor="nw",
                justify="left",
                wraplength=wraplength,
                padx=2,
                pady=0,
            )
            label.bind("<Button-1>", self._activate_editor, add="+")
            self._display_lines.append(label)

    def _scroll_rendered_text(self, action: str, value: Any, units: Any = None) -> None:
        """Use ScrollableFrame state and align scrolling to complete text lines."""
        self._text_scroller._update_scrollregion()
        _, _, _, viewport_height = self._text_scroller._viewport_geometry()
        maximum = max(0, self._text_scroller._content_extent - viewport_height)
        if maximum <= 0:
            self._text_scroller._scroll_offset = 0
            self._text_scroller._update_scrollregion()
            return

        boundaries = [0]
        offset = 0
        for label in self._display_lines:
            if label.winfo_manager() != "pack":
                continue
            offset += max(1, label._height)
            if offset < maximum:
                boundaries.append(offset)
        if boundaries[-1] != maximum:
            boundaries.append(maximum)

        current = self._text_scroller._scroll_offset
        if action == "moveto":
            target = maximum * max(0.0, min(1.0, float(value)))
            new_offset = min(boundaries, key=lambda boundary: abs(boundary - target))
        elif action == "scroll":
            current_index = min(
                range(len(boundaries)),
                key=lambda index: abs(boundaries[index] - current),
            )
            new_offset = boundaries[
                max(0, min(len(boundaries) - 1, current_index + int(value)))
            ]
        else:
            return
        self._text_scroller._scroll_offset = int(new_offset)
        self._text_scroller._update_scrollregion()

    def _sync_canvas_text(self) -> None:
        if not hasattr(self, "_text_scroller"):
            return
        show_canvas_text = self._canvas_text_enabled() and self._is_rendered
        if not show_canvas_text:
            self._text_scroller.hide()
            self.canvas.itemconfigure(
                self._window_id,
                state="normal" if self._is_rendered else "hidden",
            )
            return

        text = self._textbox.get("1.0", "end-1c")
        lines = text.split("\n")
        wraplength = max(1, getattr(self, "_display_text_width", self._width) - 4)
        self._ensure_display_lines(len(lines))
        for index, line in enumerate(lines):
            label = self._display_lines[index]
            label.configure(
                text=line if line else " ",
                text_color=self._text_color,
                font=self._font,
                wraplength=wraplength,
                height=1,
                pady=0,
            )
            if label.winfo_manager() != "pack":
                label.pack(fill="x", anchor="nw")
        for label in self._display_lines[len(lines):]:
            if label.winfo_manager() == "pack":
                label.pack_forget()
        self.canvas.itemconfigure(self._window_id, state="hidden")
        self._text_scroller.show()
        self.after_idle(self._text_scroller._update_scrollregion)

    def _on_yscroll(self, first: str, last: str) -> None:
        self._native_y_fraction = (float(first), float(last))
        if self._external_yscrollcommand is not None:
            self._external_yscrollcommand(first, last)

    def _on_xscroll(self, first: str, last: str) -> None:
        self._x_fraction = (float(first), float(last))
        if self._external_xscrollcommand is not None:
            self._external_xscrollcommand(first, last)

    def _schedule_content_layout(self) -> None:
        if self._content_layout_pending or self._destroyed:
            return
        self._content_layout_pending = True
        self.after_idle(self._flush_content_layout)

    def _flush_content_layout(self) -> None:
        self._content_layout_pending = False
        if not self._destroyed and self._is_rendered:
            self._layout_content()

    def _schedule_scrollbar_refresh(self) -> None:
        if self._scrollbar_refresh_pending or self._destroyed:
            return
        self._scrollbar_refresh_pending = True
        self.after_idle(self._flush_scrollbar_refresh)

    def _flush_scrollbar_refresh(self) -> None:
        self._scrollbar_refresh_pending = False
        if not self._destroyed and self._is_rendered:
            self._refresh_scrollbars()

    def _refresh_scrollbars(self) -> None:
        try:
            self._on_xscroll(*map(str, self._textbox.xview()))
            self._on_yscroll(*map(str, self._textbox.yview()))
        except tk.TclError:
            pass

    def _layout_content(self) -> None:
        left, top = self._winfo_origin()
        inset = max(self._corner_radius, self._border_width + self._border_spacing)
        bar = self._text_scroller._scrollbar_thickness if self._scrollbars_activated else 0
        text_width = max(1, self._width - inset * 2)
        text_height = max(1, self._height - inset * 2)
        self._text_view_width = text_width
        self._text_view_height = text_height
        physical_x, physical_y = self._physical_point(
            left + inset + text_width / 2,
            top + inset + text_height / 2,
        )
        self.canvas.coords(self._window_id, physical_x, physical_y)
        self.canvas.itemconfigure(
            self._window_id,
            width=max(1, int(round(self._apply_widget_scaling(text_width)))),
            height=max(1, int(round(self._apply_widget_scaling(text_height)))),
        )

        self._text_scroller.hide_scrollbar = not self._scrollbars_activated
        viewport_width = max(1, text_width - bar)
        self._display_text_width = viewport_width
        if (
            self._text_scroller.cget("width") != viewport_width
            or self._text_scroller.cget("height") != text_height
        ):
            self._text_scroller.configure(width=viewport_width, height=text_height)
        self._text_scroller.move(left + inset, top + inset)
        self._sync_canvas_text()

    def _redraw(self) -> None:
        radius = min(max(0, self._corner_radius), self._width // 2, self._height // 2)
        self._background.configure(
            width=self._width, height=self._height, anchor=self._anchor,
            fg_color=self._fg_color, border_radius=radius,
            border_width=self._border_width, border_color=self._border_color,
            border_padding=0, opacity=self._opacity,
        )
        surface = self._surface_color()
        text = _appearance_color(self._text_color, "#ffffff")
        self._textbox.configure(
            bg=surface, fg=text, insertbackground=text,
            selectbackground=_appearance_color(self._scrollbar_button_color, "#1f6aa5"),
            font=self._apply_font_scaling(self._font),
        )
        self._text_scroller.configure(
            fg_color="transparent",
            scrollbar_button_color=self._scrollbar_button_color,
            scrollbar_button_hover_color=self._scrollbar_button_hover_color,
        )
        if not self._is_rendered:
            self._redraw_pending = True
            return
        self._redraw_pending = False
        self._layout_content()

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        text_updates: dict[str, Any] = {}
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
            elif key == "border_spacing":
                value = int(value)
                if value != self._border_spacing: self._border_spacing, redraw = value, True
            elif key == "bg_color":
                resolved = (
                    _master_background_color(self.master, self.canvas)
                    if value == "transparent"
                    else value
                )
                if resolved != self._bg_color: self._bg_color, redraw = resolved, True
            elif key == "fg_color":
                if value != self._fg_color: self._fg_color, redraw = value, True
            elif key == "border_color":
                if value != self._border_color: self._border_color, redraw = value, True
            elif key == "text_color":
                if value != self._text_color: self._text_color, redraw = value, True
            elif key == "scrollbar_button_color":
                if value != self._scrollbar_button_color: self._scrollbar_button_color, redraw = value, True
            elif key == "scrollbar_button_hover_color":
                if value != self._scrollbar_button_hover_color: self._scrollbar_button_hover_color, redraw = value, True
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
            elif key == "activate_scrollbars":
                value = bool(value)
                if value != self._scrollbars_activated: self._scrollbars_activated, redraw = value, True
            elif key == "text_variable":
                if value is not self.text_variable:
                    self.untrace_write(); self.text_variable = value
                    if value is not None: self.trace_write(value, self._variable_changed)
            elif key == "xscrollcommand": self._external_xscrollcommand = value
            elif key == "yscrollcommand": self._external_yscrollcommand = value
            elif key in self._valid_text_attributes:
                if self._textbox.cget(key) != value: text_updates[key] = value
            else: raise ValueError(f"Unsupported Textbox option: {key!r}")
        if text_updates: self._textbox.configure(**text_updates)
        if redraw:
            self._redraw()
            self._schedule_scrollbar_refresh()
        self._sync_appearance_callback()

    config = configure

    def cget(self, attribute_name: str) -> Any:
        values = {
            "width": self._desired_width, "height": self._desired_height,
            "corner_radius": self._corner_radius, "border_width": self._border_width,
            "border_spacing": self._border_spacing, "bg_color": self._bg_color,
            "fg_color": self._fg_color, "border_color": self._border_color,
            "text_color": self._text_color, "scrollbar_button_color": self._scrollbar_button_color,
            "scrollbar_button_hover_color": self._scrollbar_button_hover_color,
            "font": self._font, "activate_scrollbars": self._scrollbars_activated,
            "text_variable": self.text_variable, "opacity": self._opacity,
        }
        if attribute_name in values: return values[attribute_name]
        if attribute_name in self._valid_text_attributes: return self._textbox.cget(attribute_name)
        raise ValueError(f"Unsupported Textbox option: {attribute_name!r}")

    def set(self, value: Any) -> None:
        state = self._textbox.cget("state")
        if state == tk.DISABLED: self._textbox.configure(state=tk.NORMAL)
        self._textbox.delete("1.0", tk.END)
        self._textbox.insert("1.0", str(value))
        if state == tk.DISABLED: self._textbox.configure(state=state)
        self._widget_changed()

    def get(self, index1: Any = "1.0", index2: Any = None) -> str:
        if index2 is None:
            return self._textbox.get(index1)
        return self._textbox.get(index1, index2)

    def insert(self, index: Any, chars: Any, *args: Any) -> Any:
        result = self._textbox.insert(index, chars, *args)
        self._widget_changed()
        return result

    def delete(self, index1: Any, index2: Any = None) -> Any:
        result = self._textbox.delete(index1, index2)
        self._widget_changed()
        return result

    def yview(self, *args: Any) -> Any:
        if not args:
            if self._canvas_text_enabled():
                return self._text_scroller._scrollbar.get()
            return self._textbox.yview()
        action = str(args[0])
        value = args[1] if len(args) > 1 else 0
        units = args[2] if len(args) > 2 else None
        if self._canvas_text_enabled():
            self._scroll_rendered_text(action, value, units)
        if action == "moveto":
            return self._textbox.yview_moveto(float(value))
        if action == "scroll":
            return self._textbox.yview_scroll(int(value), units or "units")
        return self._textbox.yview(*args)

    def yview_moveto(self, fraction: float) -> Any:
        if self._canvas_text_enabled():
            self._text_scroller.scroll_to(fraction)
        return self._textbox.yview_moveto(fraction)

    def yview_scroll(self, number: int, what: str) -> Any:
        if self._canvas_text_enabled():
            self._scroll_rendered_text("scroll", number, what)
        return self._textbox.yview_scroll(number, what)

    def see(self, index: Any) -> Any:
        result = self._textbox.see(index)
        if self._canvas_text_enabled():
            target = self._textbox.index(index)
            line = max(1, int(target.split(".")[0]))
            total = max(1, int(self._textbox.index("end-1c").split(".")[0]))
            fraction = 1.0 if line >= total else (line - 1) / max(1, total - 1)
            self.after_idle(lambda: self._text_scroller.scroll_to(fraction))
        return result

    def _build_context_menu(self) -> tk.Menu:
        menu = tk.Menu(self._textbox, tearoff=False)
        menu.add_command(label="Cut", command=lambda: self._textbox.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: self._textbox.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: self._textbox.event_generate("<<Paste>>"))
        menu.add_separator(); menu.add_command(label="Select All", command=self.select_all)
        return menu

    def select_all(self) -> str:
        self._textbox.tag_add("sel", "1.0", tk.END)
        return "break"

    def show_context_menu(self, event: tk.Event) -> str:
        self._context_menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _set_anchor(self, anchor: str) -> None:
        self._anchor = str(anchor); self._background.configure(anchor=self._anchor)

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
        self._schedule_scrollbar_refresh()

    def _resize_for_place(self, width: int | None, height: int | None) -> None:
        self._apply_geometry_allocation(width, height)

    def winfo_reqwidth(self) -> int:
        return max(1, int(round(self._apply_widget_scaling(self._desired_width))))

    def winfo_reqheight(self) -> int:
        return max(1, int(round(self._apply_widget_scaling(self._desired_height))))

    def move(self, x: int, y: int) -> None:
        self._x, self._y = int(x), int(y); self._background.move(self._x, self._y); self._redraw()

    def bind(self, sequence: str | None = None, command: Callable | None = None, add: str | bool = True) -> Any:
        if self._is_lifecycle_event(sequence):
            return self._bind_lifecycle_event(sequence, command, add)
        if add not in ("+", True): raise ValueError("'add' argument can only be '+' or True")
        return self._textbox.bind(sequence, command, add="+")

    def unbind(self, sequence: str | None = None, funcid: str | None = None) -> None:
        if self._is_lifecycle_event(sequence):
            self._unbind_lifecycle_event(sequence, funcid)
            return
        if funcid is not None: raise ValueError("'funcid' must be None")
        self._textbox.unbind(sequence)

    def __getattr__(self, name: str) -> Any:
        textbox = self.__dict__.get("_textbox")
        if textbox is not None and hasattr(textbox, name):
            return getattr(textbox, name)
        return super().__getattr__(name)

    def focus(self) -> Any:
        self._editor_active = True; self._sync_canvas_text(); return self._textbox.focus()
    def focus_set(self) -> Any:
        self._editor_active = True; self._sync_canvas_text(); return self._textbox.focus_set()
    def focus_force(self) -> Any:
        self._editor_active = True; self._sync_canvas_text(); return self._textbox.focus_force()

    def _hide(self) -> None:
        if self._appearance_callback_registered:
            AppearanceModeTracker.remove(self._set_appearance_mode)
            self._appearance_callback_registered = False
        self.canvas.itemconfigure(self._window_id, state="hidden")
        self._text_scroller.hide()
    def _show(self) -> None:
        self._redraw()
        self._sync_appearance_callback()
        self._schedule_scrollbar_refresh()

    def destroy(self) -> None:
        if self._appearance_callback_registered:
            AppearanceModeTracker.remove(self._set_appearance_mode)
            self._appearance_callback_registered = False
        self._font.remove_size_configure_callback(self._font_changed)
        self._remove_scroll_bindings()
        self._detach_layout(); self._cleanup_canvas_element()
        self.canvas.delete(self._window_id); self._textbox.destroy()


__all__ = ["Textbox"]
