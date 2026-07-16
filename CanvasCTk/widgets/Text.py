from ._shared import *
from .Item import Item

class Text(Item):
    def __init__(
        self,
        master: Any,
        font: str | tuple = ("Roboto", 14),
        fill: Any = None,
        activefill: Any = None,
        disabledfill: Any = None,
        justify: str = "left",
        state: str = "normal",
        tags: str | tuple = "",
        width: int = 0,
        text: str = "",
        canvas: tk.Canvas | None = None,
        anchor: str = "center",
        x: int = 0,
        y: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, canvas, **kwargs)
        theme_text_color = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        uses_theme_fill = fill is None
        uses_theme_activefill = activefill is None
        uses_theme_disabledfill = disabledfill is None
        fill = theme_text_color if fill is None else fill
        activefill = fill if activefill is None else activefill
        disabledfill = fill if disabledfill is None else disabledfill
        self._track_theme_defaults(
            "CTkLabel",
            fill="text_color" if uses_theme_fill else False,
            activefill="text_color" if uses_theme_activefill else False,
            disabledfill="text_color" if uses_theme_disabledfill else False,
        )
        if isinstance(font, str):
            match = re.fullmatch(r"(.+?)\s+(\d+)(?:\s+(\w+))?", font.strip())
            if not match:
                raise ValueError(f"Font must look like 'Roboto 14 bold': {font!r}")
            family, size, weight = match.groups()
            font = (family, int(size), weight) if weight else (family, int(size))
        if isinstance(font, ctk.CTkFont):
            self._font = font
        else:
            self._font = ctk.CTkFont(family=font[0], size=font[1], weight=font[2] if len(font) > 2 else "normal")
        self._font.add_size_configure_callback(self._font_changed)
        self.fill = fill
        self.activefill = activefill
        self.disabledfill = disabledfill
        self._current_fill = fill
        self._state = str(state)
        self._anchor = anchor
        self._wraplength = max(0, int(width))
        self._text_value = ""
        physical_x, physical_y = self._physical_point(x, y)
        self._text_id = self.canvas.create_text(
            physical_x, physical_y, text=text, font=self._apply_font_scaling(self._font),
            fill=_appearance_color(fill, "black"),
            activefill=_appearance_color(self.activefill, "black"),
            disabledfill=_appearance_color(self.disabledfill, "black"),
            justify=justify, state="hidden", tags=tags,
            width=self._apply_widget_scaling(self._wraplength), anchor=anchor,
        )
        self._x, self._y = x, y
        self._appearance_callback_registered = False
        self.set(text)

    def _sync_appearance_callback(self) -> None:
        needed = self._is_rendered and any(
            isinstance(color, (tuple, list))
            for color in (self._current_fill, self.activefill, self.disabledfill)
        )
        if needed and not self._appearance_callback_registered:
            AppearanceModeTracker.add(self._set_appearance_mode, self.canvas)
            self._appearance_callback_registered = True
        elif not needed and self._appearance_callback_registered:
            AppearanceModeTracker.remove(self._set_appearance_mode)
            self._appearance_callback_registered = False

    def _font_changed(self) -> None:
        if hasattr(self, "_text_id"):
            self.canvas.itemconfigure(self._text_id, font=self._apply_font_scaling(self._font))
            if self._update_dimensions() and self._canvas_host is not None and self._layout_manager:
                self._canvas_host._schedule_child_layout()

    def _on_widget_scaling_changed(self, old_scaling: float, new_scaling: float) -> None:
        super()._on_widget_scaling_changed(old_scaling, new_scaling)
        if hasattr(self, "_text_id"):
            self.canvas.itemconfigure(
                self._text_id,
                font=self._apply_font_scaling(self._font),
                width=self._apply_widget_scaling(self._wraplength),
            )
            self.move(self._x, self._y)
            self._update_dimensions()

    def _update_dimensions(self) -> bool:
        previous = self.canvas.itemcget(self._text_id, "state")
        was_hidden = previous == "hidden"
        physical_x, physical_y = self._physical_point(self._x, self._y)
        if was_hidden:
            # Tk excludes hidden canvas text from bbox calculations. Measure it
            # far outside the viewport so the temporary normal state can never
            # flash at the widget's not-yet-laid-out (usually 0, 0) position.
            _position_canvas_text(
                self.canvas,
                self._text_id,
                -100_000,
                -100_000,
                self._anchor,
            )
            self.canvas.itemconfigure(self._text_id, state="normal")
        else:
            _position_canvas_text(
                self.canvas,
                self._text_id,
                physical_x,
                physical_y,
                self._anchor,
            )
        try:
            bounds = self.canvas.bbox(self._text_id)
        finally:
            if was_hidden:
                self.canvas.itemconfigure(self._text_id, state="hidden")
                _position_canvas_text(
                    self.canvas,
                    self._text_id,
                    physical_x,
                    physical_y,
                    self._anchor,
                )
        if bounds is None:
            return False
        dimensions = (
            int(round(self._reverse_widget_scaling(bounds[2] - bounds[0]))),
            int(round(self._reverse_widget_scaling(bounds[3] - bounds[1]))),
        )
        changed = dimensions != (self._width, self._height)
        self._width, self._height = dimensions
        return changed

    def configure(self, **kwargs: Any) -> None:
        dimensions_changed = False
        if "state" in kwargs:
            state = str(kwargs["state"])
            if state == self._state:
                kwargs.pop("state")
            else:
                self._state = state
        if "state" in kwargs:
            kwargs["state"] = "hidden" if not self._is_rendered else self._state
        if "fill" in kwargs:
            fill = kwargs["fill"]
            if fill == self.fill:
                kwargs.pop("fill")
            else:
                self.fill = fill
                self._current_fill = fill
                kwargs["fill"] = _appearance_color(fill, "black")
        if "activefill" in kwargs:
            activefill = kwargs["activefill"]
            if activefill == self.activefill:
                kwargs.pop("activefill")
            else:
                self.activefill = activefill
                kwargs["activefill"] = _appearance_color(activefill, "black")
        if "disabledfill" in kwargs:
            disabledfill = kwargs["disabledfill"]
            if disabledfill == self.disabledfill:
                kwargs.pop("disabledfill")
            else:
                self.disabledfill = disabledfill
                kwargs["disabledfill"] = _appearance_color(disabledfill, "black")
        if "font" in kwargs:
            value = kwargs["font"]
            if isinstance(value, ctk.CTkFont):
                if value is self._font:
                    kwargs.pop("font")
                else:
                    self._font.remove_size_configure_callback(self._font_changed)
                    self._font = value
                    self._font.add_size_configure_callback(self._font_changed)
                    dimensions_changed = True
            else:
                desired = (value[0], value[1], value[2] if len(value) > 2 else "normal")
                current = tuple(self._font.cget(name) for name in ("family", "size", "weight"))
                if desired == current:
                    kwargs.pop("font")
                else:
                    # CTkFont.configure() invokes its registered callbacks.
                    # This configure call already updates the canvas once with
                    # all text options, so suppress the otherwise duplicate
                    # itemconfigure/bbox pass from _font_changed().
                    self._font.remove_size_configure_callback(self._font_changed)
                    try:
                        self._font.configure(family=desired[0], size=desired[1], weight=desired[2])
                    finally:
                        self._font.add_size_configure_callback(self._font_changed)
                    dimensions_changed = True
            if "font" in kwargs:
                kwargs["font"] = self._apply_font_scaling(self._font)
        if "width" in kwargs:
            wraplength = max(0, int(kwargs["width"]))
            if wraplength == self._wraplength:
                kwargs.pop("width")
            else:
                self._wraplength = wraplength
                kwargs["width"] = self._apply_widget_scaling(wraplength)
                dimensions_changed = True
        if "text" in kwargs:
            text = str(kwargs["text"])
            if text == self._text_value:
                kwargs.pop("text")
            else:
                self._text_value = text
                kwargs["text"] = text
                dimensions_changed = True
        if "justify" in kwargs:
            dimensions_changed = True
        if not kwargs:
            return
        self.canvas.itemconfigure(self._text_id, **kwargs)
        if dimensions_changed and self._update_dimensions() and self._canvas_host is not None and self._layout_manager:
            self._canvas_host._schedule_child_layout()
        self._sync_appearance_callback()

    config = configure

    def move(self, x: int, y: int) -> None:
        self._x, self._y = x, y
        physical_x, physical_y = self._physical_point(x, y)
        _position_canvas_text(self.canvas, self._text_id, physical_x, physical_y, self._anchor)

    def _set_anchor(self, anchor: str) -> None:
        self._anchor = anchor
        self.canvas.itemconfigure(self._text_id, anchor=anchor)
        self.move(self._x, self._y)

    def set(self, text: str) -> None:
        self.configure(text=text)

    def bind(self, sequence: str, func: Callable, add: str | None = None) -> str:
        if self._is_lifecycle_event(sequence):
            return self._bind_lifecycle_event(sequence, func, add)
        return self.canvas.tag_bind(self._text_id, sequence, func, add=add)

    def unbind(self, sequence: str, funcid: str | None = None) -> None:
        if self._is_lifecycle_event(sequence):
            self._unbind_lifecycle_event(sequence, funcid)
            return
        self.canvas.tag_unbind(self._text_id, sequence, funcid)

    def force_normal(self) -> None:
        self._state = "normal"
        self.canvas.itemconfigure(
            self._text_id,
            state="normal" if self._is_rendered else "hidden",
        )
        self._set_current_fill(self.fill)

    def force_active(self) -> None:
        self._state = "normal"
        self.canvas.itemconfigure(
            self._text_id,
            state="normal" if self._is_rendered else "hidden",
        )
        self._set_current_fill(self.activefill)

    def force_disabled(self) -> None:
        self._state = "disabled"
        self.canvas.itemconfigure(
            self._text_id,
            state="disabled" if self._is_rendered else "hidden",
        )
        self._set_current_fill(self.disabledfill)

    def _set_current_fill(self, color: Any) -> None:
        self._current_fill = color
        self.canvas.itemconfigure(self._text_id, fill=_appearance_color(color, "black"))

    def _set_appearance_mode(self, _: str | None = None) -> None:
        self.canvas.itemconfigure(
            self._text_id,
            fill=_appearance_color(self._current_fill, "black"),
            activefill=_appearance_color(self.activefill, "black"),
            disabledfill=_appearance_color(self.disabledfill, "black"),
        )

    def _hide(self) -> None:
        if self._appearance_callback_registered:
            AppearanceModeTracker.remove(self._set_appearance_mode)
            self._appearance_callback_registered = False
        self.canvas.itemconfigure(self._text_id, state="hidden")

    def _show(self) -> None:
        self._set_appearance_mode()
        self.canvas.itemconfigure(self._text_id, state=self._state)
        self._sync_appearance_callback()

    def destroy(self) -> None:
        self._detach_layout()
        if self._appearance_callback_registered:
            AppearanceModeTracker.remove(self._set_appearance_mode)
            self._appearance_callback_registered = False
        self._font.remove_size_configure_callback(self._font_changed)
        self._cleanup_canvas_element()
        self.canvas.delete(self._text_id)


