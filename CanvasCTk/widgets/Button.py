from ._shared import *
from ._shared import _master_background_color
from .Image import Image
from .Item import Item
from .Text import Text

class Button(Item):
    def __init__(
        self,
        master: Any,
        width: int = 140,
        height: int = 28,
        corner_radius: int | None = None,
        border_width: int | None = None,
        border_spacing: int = 2,
        bg_color: Any = "transparent",
        fg_color: Any = None,
        hover_color: Any = None,
        border_color: Any = None,
        text_color: Any = None,
        text_color_disabled: Any = None,
        background_corner_colors: Any = None,
        round_width_to_even_numbers: bool = True,
        round_height_to_even_numbers: bool = True,
        text: str = "CTkButton",
        font: str | tuple | ctk.CTkFont | None = None,
        textvariable: tk.Variable | None = None,
        image: str | Path | PILImage.Image | None = None,
        state: str = "normal",
        hover: bool = True,
        command: Callable[[], Any] | None = None,
        compound: str = "left",
        anchor: str = "center",
        *,
        disabled: bool = False,
        size: tuple[int, int] | None = None,
        wraplength: int = 0,
        justify: str = "center",
        fill: Any = None,
        activefill: Any = None,
        disabledfill: Any = None,
        select_color: Any = None,
        disabled_color: Any = None,
        border_radius: int | None = None,
        border_hover_color: Any = None,
        border_selected_color: Any = None,
        border_disabled_color: Any = None,
        bg_normal_opacity: float = 1,
        bg_hover_opacity: float | None = None,
        bg_selected_opacity: float | None = None,
        bg_disabled_opacity: float | None = None,
        button_normal_opacity: float = 1,
        button_hover_opacity: float | None = None,
        button_selected_opacity: float | None = None,
        button_disabled_opacity: float | None = None,
        bg_normal_brightness: float = 1,
        bg_hover_brightness: float | None = None,
        bg_selected_brightness: float | None = None,
        bg_disabled_brightness: float | None = None,
        button_normal_brightness: float = 1,
        button_hover_brightness: float | None = None,
        button_selected_brightness: float | None = None,
        button_disabled_brightness: float | None = None,
        auto_width: bool | None = None,
        text_padding: Any = (14, 14),
        canvas: tk.Canvas | None = None,
        x: int = 40,
        y: int = 40,
        **kwargs: Any,
    ) -> None:
        if corner_radius is not None:
            border_radius = int(corner_radius)
        if text_color is not None and fill is None:
            fill = text_color
        if text_color_disabled is not None and disabledfill is None:
            disabledfill = text_color_disabled
        font = ctk.CTkFont() if font is None else font
        theme = ctk.ThemeManager.theme["CTkButton"]
        theme_defaults: dict[str, bool | str | tuple[str, ...]] = {
            "fg_color": fg_color is None,
            "hover_color": hover_color is None,
            "select_color": ("select_color", "fg_color") if select_color is None else False,
            "disabled_color": "fg_color" if disabled_color is None else False,
            "border_color": border_color is None,
            "corner_radius": border_radius is None,
            "border_width": border_width is None,
            "text_color": fill is None,
            "text_color_hovered": ("text_color_hovered", "text_color") if activefill is None else False,
            "text_color_disabled": disabledfill is None,
        }
        super().__init__(master, canvas, **kwargs)
        fg_color = theme["fg_color"] if fg_color is None else fg_color
        hover_color = theme["hover_color"] if hover_color is None else hover_color
        select_color = theme.get("select_color", fg_color) if select_color is None else select_color
        disabled_color = fg_color if disabled_color is None else disabled_color
        border_color = theme["border_color"] if border_color is None else border_color
        fill = theme["text_color"] if fill is None else fill
        activefill = theme.get("text_color_hovered", fill) if activefill is None else activefill
        disabledfill = theme["text_color_disabled"] if disabledfill is None else disabledfill
        border_radius = int(theme["corner_radius"] if border_radius is None else border_radius)
        border_width = int(theme["border_width"] if border_width is None else border_width)
        self._track_theme_defaults("CTkButton", **theme_defaults)
        explicit_width = width is not None
        button_width = int(width if width is not None else 64)
        button_height = int(height if height is not None else (28 if text and image is None else 64))
        self.image = image
        self.command = command
        if state not in ("normal", "disabled"):
            raise ValueError("Button state must be 'normal' or 'disabled'.")
        self.disabled = bool(disabled) or state == "disabled"
        self._hover_enabled = bool(hover)
        self.selected = False
        self.hovered = False
        self._pressed = False
        self._wraplength = max(0, int(wraplength))
        self._justify = str(justify)
        self._font_value = font
        self._text_color = fill
        self._text_color_hovered = activefill
        self._text_color_disabled = disabledfill
        self._text_value = (
            str(textvariable.get())
            if textvariable is not None and textvariable != ""
            else ("" if text is None else str(text))
        )
        self._textvariable = textvariable
        self._compound = str(compound)
        self._bg_color_transparent = bg_color == "transparent"
        self._bg_color = (
            _master_background_color(master, self.canvas)
            if self._bg_color_transparent
            else bg_color
        )
        self._background_corner_colors = background_corner_colors
        self._corner_background_ids: list[int] = []
        self._outer_background_id: int | None = None
        self._canvas_background_tracker_registered = False
        self._event_tag = f"canvasctk_button_{id(self)}"
        self._round_width_to_even_numbers = bool(round_width_to_even_numbers)
        self._round_height_to_even_numbers = bool(round_height_to_even_numbers)
        self._text_padding = text_padding
        self._auto_width = bool(self._text_value) and not explicit_width if auto_width is None else bool(auto_width)
        self._x, self._y = int(x), int(y)
        self._anchor = "center"
        self._content_anchor = str(anchor)
        self._width, self._height = button_width, button_height
        self._border_radius = int(border_radius)
        self._border_width = int(border_width)
        self._border_spacing = int(border_spacing)
        if size is not None and len(size) != 2:
            raise ValueError("Button size must be a (width, height) tuple.")
        self._image_size_explicit = size is not None
        self._image_size_follows_button = size is None and not isinstance(image, ctk.CTkImage)
        self._ctk_image_source: ctk.CTkImage | None = None
        if size is not None:
            image_size = size
        elif isinstance(image, ctk.CTkImage):
            image_size = image.cget("size")
        else:
            image_size = (self._width, self._height)
        self._image_size = tuple(map(int, image_size))
        self._colors = {
            "normal": fg_color,
            "hover": hover_color,
            "selected": select_color,
            "disabled": disabled_color,
        }
        self._border_colors = {
            "normal": border_color,
            "hover": border_hover_color,
            "selected": border_selected_color,
            "disabled": border_disabled_color,
        }
        self._bg_opacity = {
            "normal": bg_normal_opacity,
            "hover": bg_hover_opacity if bg_hover_opacity is not None else bg_normal_opacity,
            "selected": bg_selected_opacity if bg_selected_opacity is not None else bg_normal_opacity,
            "disabled": bg_disabled_opacity if bg_disabled_opacity is not None else bg_normal_opacity,
        }
        self._button_opacity = {
            "normal": button_normal_opacity,
            "hover": button_hover_opacity if button_hover_opacity is not None else button_normal_opacity,
            "selected": button_selected_opacity if button_selected_opacity is not None else button_normal_opacity,
            "disabled": button_disabled_opacity if button_disabled_opacity is not None else button_normal_opacity,
        }
        self._bg_brightness = {
            "normal": bg_normal_brightness,
            "hover": bg_hover_brightness if bg_hover_brightness is not None else bg_normal_brightness,
            "selected": bg_selected_brightness if bg_selected_brightness is not None else bg_normal_brightness,
            "disabled": bg_disabled_brightness if bg_disabled_brightness is not None else bg_normal_brightness,
        }
        self._button_brightness = {
            "normal": button_normal_brightness,
            "hover": button_hover_brightness if button_hover_brightness is not None else button_normal_brightness,
            "selected": button_selected_brightness if button_selected_brightness is not None else button_normal_brightness,
            "disabled": button_disabled_brightness if button_disabled_brightness is not None else button_normal_brightness,
        }
        if self._auto_width:
            self._width = self._preferred_width()
            if self._image_size_follows_button:
                self._image_size = (self._width, self._height)
        self._background = self.put(Image(
            master,
            canvas=self.canvas,
            width=self._width,
            height=self._height,
            anchor=self._anchor,
            x=x,
            y=y,
            fg_color=fg_color,
            border_radius=border_radius,
            opacity=bg_normal_opacity,
        ))
        # The foreground already spans the complete button. Keep it as the hit
        # surface even when fg_color is transparent instead of allocating a
        # second, permanently transparent full-size image.
        self._background._enable_event_surface()
        self.canvas.addtag_withtag(self._event_tag, self._background._image_id)
        layer_width, layer_height = self._fit_image_size()
        self._image_layer: Image | None = None
        self._border_layer: Image | None = None
        self._text: Text | None = None
        if image is not None:
            self._ensure_image_layer(layer_width, layer_height)
        if self._border_is_visible("normal"):
            self._ensure_border_layer("normal")
        if self._text_value:
            self._ensure_text_layer()
        self._set_ctk_image_source(image)
        self._create_bindings()
        self._apply_state()
        self._layout_content()
        self._sync_canvas_backgrounds()
        self._restack_layers()
        if textvariable is not None:
            self.trace_write(textvariable, lambda value: self.configure(text=value))

    def _state(self) -> str:
        if self.disabled:
            return "disabled"
        if self.selected:
            return "selected"
        if self.hovered:
            return "hover"
        return "normal"

    def _discard_layer(self, layer: Any) -> None:
        if layer is None:
            return
        layer_id = getattr(layer, "_id", None)
        try:
            layer.destroy()
        finally:
            if layer_id is not None:
                self.elements.pop(layer_id, None)
            self._element_identity_keys.pop(id(layer), None)

    def _ensure_image_layer(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> Image:
        if self._image_layer is None:
            layer_width, layer_height = self._fit_image_size()
            width = layer_width if width is None else width
            height = layer_height if height is None else height
            self._image_layer = self.put(Image(
                self.master,
                canvas=self.canvas,
                image=self.image,
                width=width,
                height=height,
                anchor=self._anchor,
                x=self._x,
                y=self._y,
                border_radius=self._image_border_radius(width, height),
                border_padding=0,
                opacity=self._button_opacity[self._state()],
                brightness=self._button_brightness[self._state()],
            ))
            self.canvas.addtag_withtag(self._event_tag, self._image_layer._image_id)
            if self._is_rendered:
                self._image_layer.show()
            self._restack_layers()
        return self._image_layer

    def _border_is_visible(self, state: str) -> bool:
        return self._border_width > 0 and Image._color_is_visible(
            self._border_color_for(state), 1,
        )

    def _ensure_border_layer(self, state: str) -> Image:
        if self._border_layer is None:
            width, height, radius = self._border_geometry()
            self._border_layer = self.put(Image(
                self.master,
                canvas=self.canvas,
                width=width,
                height=height,
                anchor=self._anchor,
                x=self._x,
                y=self._y,
                border_radius=radius,
                border_width=self._border_width,
                border_color=self._border_color_for(state),
            ))
            self.canvas.addtag_withtag(self._event_tag, self._border_layer._image_id)
            if self._is_rendered:
                self._border_layer.show()
            self._restack_layers()
        return self._border_layer

    def _ensure_text_layer(self) -> Text:
        if self._text is None:
            self._text = self.put(Text(
                self.master,
                font=self._font_value,
                text=self._text_value,
                anchor="center",
                canvas=self.canvas,
                x=self._x,
                y=self._y,
                width=self._wraplength,
                justify=self._justify,
                fill=self._text_color,
                activefill=self._text_color_hovered,
                disabledfill=self._text_color_disabled,
            ))
            self.canvas.addtag_withtag(self._event_tag, self._text._text_id)
            if self._is_rendered:
                self._text.show()
            self._restack_layers()
        return self._text

    def _restack_layers(self) -> None:
        if self._destroyed or not hasattr(self, "_background"):
            return
        background_id = self._background._image_id

        def exists(item_id: Any) -> bool:
            try:
                return item_id is not None and bool(self.canvas.find_withtag(item_id))
            except tk.TclError:
                return False

        if not exists(background_id):
            return
        try:
            for item_id in self._corner_background_ids:
                if exists(item_id):
                    self.canvas.tag_lower(item_id, background_id)
            if exists(self._outer_background_id):
                self.canvas.tag_lower(self._outer_background_id, background_id)
            previous = background_id
            for layer in (self._image_layer, self._border_layer):
                if layer is not None and exists(layer._image_id):
                    self.canvas.tag_raise(layer._image_id, previous)
                    previous = layer._image_id
            if self._text is not None and exists(self._text._text_id):
                self.canvas.tag_raise(self._text._text_id, previous)
        except tk.TclError:
            # A queued layout can overlap destruction of a shared canvas.
            return

    def _create_bindings(self, sequence: str | None = None) -> None:
        bindings = {
            "<Enter>": self._on_enter,
            "<Leave>": self._on_leave,
            "<ButtonPress-1>": self._on_press,
            "<ButtonRelease-1>": self._on_release,
        }
        for event, callback in bindings.items():
            if sequence is None or sequence == event:
                self.canvas.tag_bind(self._event_tag, event, callback, add="+")

    def _sync_background_corners(self) -> None:
        """Paint CTkButton's optional four square background quadrants."""
        colors = self._background_corner_colors
        if colors is None:
            for item_id in self._corner_background_ids:
                self.canvas.delete(item_id)
            self._corner_background_ids.clear()
            return
        if not isinstance(colors, (tuple, list)) or len(colors) != 4:
            raise ValueError("background_corner_colors must contain four colors")
        while len(self._corner_background_ids) < 4:
            item_id = self.canvas.create_rectangle(
                0, 0, 1, 1, outline="", state="hidden",
                tags=(self._event_tag,),
            )
            self._corner_background_ids.append(item_id)

        left, top = self._winfo_origin()
        left_width = round(self._width / 2)
        right_width = self._width - left_width
        top_height = round(self._height / 2)
        bottom_height = self._height - top_height
        geometry = (
            (left, top, left + left_width, top + top_height),
            (left + left_width, top, left + self._width, top + top_height),
            (left + left_width, top + top_height, left + self._width, top + self._height),
            (left, top + top_height, left + left_width, top + self._height),
        )
        state = "normal" if self._is_rendered else "hidden"
        for item_id, color, box in zip(self._corner_background_ids, colors, geometry):
            x0, y0 = self._physical_point(box[0], box[1])
            x1, y1 = self._physical_point(box[2], box[3])
            self.canvas.coords(item_id, x0, y0, x1, y1)
            self.canvas.itemconfigure(
                item_id,
                fill=_appearance_color(color, str(self.canvas.cget("bg"))),
                state=state,
            )
            self.canvas.tag_lower(item_id, self._background._image_id)

    def _sync_outer_background(self) -> None:
        needed = (
            not self._bg_color_transparent
            and self._background_corner_colors is None
        )
        if not needed:
            if self._outer_background_id is not None:
                self.canvas.delete(self._outer_background_id)
                self._outer_background_id = None
            return
        if self._outer_background_id is None:
            self._outer_background_id = self.canvas.create_rectangle(
                0, 0, 1, 1, outline="", state="hidden",
                tags=(self._event_tag,),
            )
        left, top = self._winfo_origin()
        x0, y0 = self._physical_point(left, top)
        x1, y1 = self._physical_point(left + self._width, top + self._height)
        self.canvas.coords(self._outer_background_id, x0, y0, x1, y1)
        self.canvas.itemconfigure(
            self._outer_background_id,
            fill=_appearance_color(self._bg_color, str(self.canvas.cget("bg"))),
            state="normal" if self._is_rendered else "hidden",
        )
        self.canvas.tag_lower(self._outer_background_id, self._background._image_id)

    def _sync_canvas_backgrounds(self, *_: Any) -> None:
        self._sync_outer_background()
        self._sync_background_corners()
        self._restack_layers()

    @staticmethod
    def _has_appearance_pair(color: Any) -> bool:
        return isinstance(color, (tuple, list)) and len(color) >= 2

    def _canvas_background_needs_tracker(self) -> bool:
        if (
            not self._bg_color_transparent
            and self._background_corner_colors is None
            and self._has_appearance_pair(self._bg_color)
        ):
            return True
        colors = self._background_corner_colors
        return bool(
            isinstance(colors, (tuple, list))
            and len(colors) == 4
            and any(self._has_appearance_pair(color) for color in colors)
        )

    def _update_canvas_background_tracker(self) -> None:
        needed = self._is_rendered and self._canvas_background_needs_tracker()
        if needed and not self._canvas_background_tracker_registered:
            AppearanceModeTracker.add(self._sync_canvas_backgrounds, self.canvas)
            self._canvas_background_tracker_registered = True
        elif not needed and self._canvas_background_tracker_registered:
            AppearanceModeTracker.remove(self._sync_canvas_backgrounds)
            self._canvas_background_tracker_registered = False

    def _set_ctk_image_source(self, image: Any) -> None:
        if self._ctk_image_source is not None:
            try:
                self._ctk_image_source.remove_configure_callback(self._ctk_image_changed)
            except ValueError:
                pass
            self._ctk_image_source = None
        if isinstance(image, ctk.CTkImage):
            self._ctk_image_source = image
            image.add_configure_callback(self._ctk_image_changed)

    def _ctk_image_changed(self) -> None:
        if self._image_size_explicit or not isinstance(self.image, ctk.CTkImage):
            return
        self._image_size = tuple(map(int, self.image.cget("size")))
        layer_width, layer_height = self._fit_image_size()
        image_layer = self._ensure_image_layer(layer_width, layer_height)
        image_layer.configure(
            width=layer_width,
            height=layer_height,
            border_radius=self._image_border_radius(layer_width, layer_height),
            border_padding=0,
        )
        self._layout_content()
        self._notify_layout_changed()

    def _on_widget_scaling_changed(self, old_scaling: float, new_scaling: float) -> None:
        super()._on_widget_scaling_changed(old_scaling, new_scaling)
        if self._image_layer is not None:
            self._ctk_image_changed()
            self._layout_content()

    def _apply_visual_state(self, state: str) -> None:
        self._background.configure(
            fg_color=self._colors[state],
            opacity=self._bg_opacity[state],
            brightness=self._bg_brightness[state],
        )
        if self._image_layer is not None:
            self._image_layer.configure(
                opacity=self._button_opacity[state],
                brightness=self._button_brightness[state],
            )
        if self._border_is_visible(state):
            border_layer = self._ensure_border_layer(state)
            border_width, border_height, border_radius = self._border_geometry()
            border_layer.configure(
                width=border_width,
                height=border_height,
                border_radius=border_radius,
                border_width=self._border_width,
                border_color=self._border_color_for(state),
            )
        elif self._border_layer is not None:
            self._discard_layer(self._border_layer)
            self._border_layer = None
        if self._text:
            if state == "disabled":
                self._text.force_disabled()
            elif state in ("hover", "selected"):
                self._text.force_active()
            else:
                self._text.force_normal()
        self._restack_layers()

    def _apply_state(self) -> None:
        self._apply_visual_state(self._state())

    def _paint(self, color: Any) -> None:
        self._background.configure(fg_color=color)

    def _border_color_for(self, state: str) -> Any:
        color = self._border_colors.get(state)
        return self._border_colors["normal"] if color is None else color

    def _image_border_radius(self, layer_width: int, layer_height: int) -> int:
        if layer_width == self._width and layer_height == self._height:
            return self._border_radius
        return 0

    def _border_geometry(self) -> tuple[int, int, int]:
        spacing = self._border_spacing
        return (
            max(1, self._width + spacing * 2),
            max(1, self._height + spacing * 2),
            max(0, self._border_radius + spacing),
        )

    @staticmethod
    def _coerce_font(font: str | tuple | ctk.CTkFont) -> ctk.CTkFont:
        if isinstance(font, ctk.CTkFont):
            return font
        if isinstance(font, str):
            match = re.fullmatch(r"(.+?)\s+(\d+)(?:\s+(\w+))?", font.strip())
            if not match:
                raise ValueError(f"Font must look like 'Roboto 14 bold': {font!r}")
            family, size, weight = match.groups()
            return ctk.CTkFont(family=family, size=int(size), weight=weight or "normal")
        return ctk.CTkFont(family=font[0], size=font[1], weight=font[2] if len(font) > 2 else "normal")

    def _preferred_width(self) -> int:
        if not self._text_value:
            return self._width
        font = self._coerce_font(self._font_value)
        lines = self._text_value.splitlines() or [self._text_value]
        text_width = max(font.measure(line) for line in lines)
        if self._wraplength > 0:
            text_width = min(text_width, self._wraplength)
        padx0, padx1 = _padding_pair(self._text_padding)
        image_width = int(self._image_size[0]) if self.image is not None else 0
        return max(1, int(self._width), image_width, int(text_width + padx0 + padx1))

    def _fit_image_size(self) -> tuple[int, int]:
        source_width = max(1, int(self._image_size[0]))
        source_height = max(1, int(self._image_size[1]))
        available_width = max(1, int(self._width))
        available_height = max(1, int(self._height))
        return min(source_width, available_width), min(source_height, available_height)

    def _content_padding(self) -> tuple[int, int]:
        return (
            max(self._border_radius, self._border_width + 1),
            self._border_width + 1,
        )

    def _layout_content(self) -> None:
        if self._text is None:
            return
        text_width = self._text._width
        text_height = self._text._height
        left, top = self._winfo_origin()
        right, bottom = left + self._width, top + self._height
        horizontal_padding, vertical_padding = self._content_padding()
        anchor = self._content_anchor.lower()

        if anchor in {"w", "nw", "sw"}:
            text_x = left + horizontal_padding + text_width / 2
        elif anchor in {"e", "ne", "se"}:
            text_x = right - horizontal_padding - text_width / 2
        else:
            text_x = (left + right) / 2

        if anchor in {"n", "ne", "nw"}:
            text_y = top + vertical_padding + text_height / 2
        elif anchor in {"s", "se", "sw"}:
            text_y = bottom - vertical_padding - text_height / 2
        else:
            text_y = (top + bottom) / 2

        self._text.move(int(round(text_x)), int(round(text_y)))

    def _notify_layout_changed(self) -> None:
        if self._canvas_host is not None:
            self._canvas_host._relayout_children()
        else:
            self._schedule_canvas_layout()

    def _resize_for_place(self, width: int | None, height: int | None) -> None:
        updates: dict[str, int] = {}
        if width is not None and width != self._width:
            updates["width"] = width
        if height is not None and height != self._height:
            updates["height"] = height
        if updates:
            self.configure(**updates)

    def _on_enter(self, _: Any = None) -> None:
        if self.disabled:
            self.canvas.configure(cursor="")
            if self.hovered:
                self.hovered = False
                self._apply_state()
            return
        self.canvas.configure(cursor="hand2")
        hovered = self._hover_enabled
        if hovered == self.hovered:
            return
        self.hovered = hovered
        self._apply_state()

    def _on_leave(self, _: Any = None) -> None:
        self.canvas.configure(cursor="")
        self._pressed = False
        if not self.hovered:
            return
        self.hovered = False
        self._apply_state()

    def _on_press(self, _: Any = None) -> None:
        if not self.disabled:
            self._pressed = True
            self._apply_visual_state("selected")

    def _pointer_inside(self, event: Any = None) -> bool:
        # Internal/programmatic release calls do not carry root coordinates;
        # preserve the hover state established by the matching press/enter.
        if event is None:
            return self.hovered
        try:
            x_root = int(getattr(event, "x_root", self.canvas.winfo_pointerx()))
            y_root = int(getattr(event, "y_root", self.canvas.winfo_pointery()))
            left = self.winfo_rootx()
            top = self.winfo_rooty()
            return (
                left <= x_root < left + self.winfo_width()
                and top <= y_root < top + self.winfo_height()
            )
        except (AttributeError, tk.TclError, TypeError, ValueError):
            return self.hovered

    def _on_release(self, event: Any = None) -> None:
        was_pressed = self._pressed
        self._pressed = False
        if self.disabled:
            return
        inside = self._pointer_inside(event)
        self.hovered = self._hover_enabled and inside
        self._apply_state()
        if was_pressed and inside and self.command:
            self.command()

    def set_selected(self, selected: bool = False) -> None:
        self.selected = selected
        self._apply_state()

    def set_disabled(self, disabled: bool = False) -> None:
        self.disabled = disabled
        if self.disabled:
            self._pressed = False
            self.hovered = False
        self._apply_state()

    def set_enabled(self, enabled: bool) -> None:
        super().set_enabled(enabled)
        self.set_disabled(not enabled)

    def invoke(self) -> Any:
        """Call the configured command unless the button is disabled."""
        if not self.disabled and self.command is not None:
            return self.command()
        return None

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        background_updates: dict[str, Any] = {}
        border_updates: dict[str, Any] = {}
        image_updates: dict[str, Any] = {}
        text_updates: dict[str, Any] = {}
        image_size_changed = False
        size_changed = False
        auto_width_changed = False
        border_geometry_changed = False
        corner_background_changed = False
        canvas_background_changed = False
        visual_state_changed = bool(require_redraw)
        layout_changed = bool(require_redraw)
        for key, value in kwargs.items():
            if key == "command":
                self.command = value
            elif key == "disabled":
                disabled = bool(value)
                if disabled != self.disabled:
                    self.disabled = disabled
                    if disabled:
                        self._pressed = False
                        self.hovered = False
                    visual_state_changed = True
            elif key == "state":
                if value not in ("normal", "disabled"):
                    raise ValueError("Button state must be 'normal' or 'disabled'.")
                disabled = value == "disabled"
                if disabled != self.disabled:
                    self.disabled = disabled
                    if disabled:
                        self.hovered = False
                    visual_state_changed = True
            elif key == "hover":
                hover_enabled = bool(value)
                if hover_enabled != self._hover_enabled:
                    self._hover_enabled = hover_enabled
                    visual_state_changed = True
                if not self._hover_enabled and self.hovered:
                    self.hovered = False
                    visual_state_changed = True
            elif key == "selected":
                selected = bool(value)
                if selected != self.selected:
                    self.selected = selected
                    visual_state_changed = True
            elif key == "width":
                self._auto_width = False
                self._desired_width = self._width = max(1, int(value))
                background_updates["width"] = self._width
                border_geometry_changed = True
                canvas_background_changed = True
                if self._image_size_follows_button:
                    self._image_size = (self._width, self._height)
                image_size_changed = True
                size_changed = True
            elif key == "height":
                self._desired_height = self._height = max(1, int(value))
                background_updates["height"] = self._height
                border_geometry_changed = True
                canvas_background_changed = True
                if self._image_size_follows_button:
                    self._image_size = (self._width, self._height)
                image_size_changed = True
                size_changed = True
            elif key == "size":
                if len(value) != 2:
                    raise ValueError("Button size must be a (width, height) tuple.")
                self._image_size = tuple(map(int, value))
                self._image_size_explicit = True
                self._image_size_follows_button = False
                image_size_changed = True
                auto_width_changed = True
                layout_changed = True
            elif key == "image":
                if value is self.image or (
                    isinstance(value, (str, Path))
                    and isinstance(self.image, (str, Path))
                    and Path(value) == Path(self.image)
                ):
                    continue
                self.image = value
                self._set_ctk_image_source(value)
                if value is None:
                    if self._image_layer is not None:
                        self._discard_layer(self._image_layer)
                        self._image_layer = None
                else:
                    image_updates["image"] = value
                if not self._image_size_explicit:
                    if isinstance(value, ctk.CTkImage):
                        self._image_size = tuple(map(int, value.cget("size")))
                        self._image_size_follows_button = False
                    else:
                        self._image_size = (self._width, self._height)
                        self._image_size_follows_button = True
                    image_size_changed = True
                auto_width_changed = True
                layout_changed = True
            elif key == "text":
                text = "" if value is None else str(value)
                if text != self._text_value:
                    self._text_value = text
                    if text:
                        text_layer = self._ensure_text_layer()
                        text_updates["text"] = text
                    elif self._text is not None:
                        self._discard_layer(self._text)
                        self._text = None
                    if self._text:
                        text_updates["text"] = text
                    auto_width_changed = True
                    layout_changed = True
            elif key == "textvariable":
                self.untrace_write()
                self._textvariable = value
                if value is not None and value != "":
                    text = str(value.get())
                    self.trace_write(value, lambda updated: self.configure(text=updated))
                    if text != self._text_value:
                        self._text_value = text
                        if text:
                            self._ensure_text_layer()
                        elif self._text is not None:
                            self._discard_layer(self._text)
                            self._text = None
                        if self._text:
                            text_updates["text"] = text
                        auto_width_changed = True
                        layout_changed = True
            elif key == "font":
                if value != self._font_value:
                    self._font_value = value
                    if self._text:
                        text_updates["font"] = value
                    auto_width_changed = True
                    layout_changed = True
            elif key == "wraplength":
                wraplength = max(0, int(value))
                if wraplength != self._wraplength:
                    self._wraplength = wraplength
                    if self._text:
                        text_updates["width"] = wraplength
                    auto_width_changed = True
                    layout_changed = True
            elif key == "justify":
                justify = str(value)
                if justify != self._justify:
                    self._justify = justify
                    if self._text:
                        text_updates["justify"] = justify
                    layout_changed = True
            elif key == "anchor":
                anchor = str(value)
                if anchor != self._content_anchor:
                    self._content_anchor = anchor
                    layout_changed = True
            elif key == "compound":
                compound = str(value)
                if compound != self._compound:
                    self._compound = compound
                    auto_width_changed = True
                    layout_changed = True
            elif key == "bg_color":
                was_transparent = self._bg_color_transparent
                self._bg_color_transparent = value == "transparent"
                bg_color = (
                    _master_background_color(self.master, self.canvas)
                    if self._bg_color_transparent
                    else value
                )
                if bg_color != self._bg_color:
                    self._bg_color = bg_color
                    canvas_background_changed = True
                if was_transparent != self._bg_color_transparent:
                    canvas_background_changed = True
            elif key == "background_corner_colors":
                if value != self._background_corner_colors:
                    self._background_corner_colors = value
                    corner_background_changed = True
                    canvas_background_changed = True
            elif key == "round_width_to_even_numbers":
                self._round_width_to_even_numbers = bool(value)
            elif key == "round_height_to_even_numbers":
                self._round_height_to_even_numbers = bool(value)
            elif key in ("fill", "text_color"):
                if value != self._text_color:
                    self._text_color = value
                    if self._text:
                        text_updates["fill"] = value
                    visual_state_changed = True
            elif key in ("activefill", "text_color_hovered", "text_color_selected"):
                if value != self._text_color_hovered:
                    self._text_color_hovered = value
                    if self._text:
                        text_updates["activefill"] = value
                    visual_state_changed = True
            elif key in ("disabledfill", "text_color_disabled"):
                if value != self._text_color_disabled:
                    self._text_color_disabled = value
                    if self._text:
                        text_updates["disabledfill"] = value
                    visual_state_changed = True
            elif key == "auto_width":
                self._auto_width = bool(value)
                auto_width_changed = True
            elif key == "text_padding":
                self._text_padding = value
                auto_width_changed = True
            elif key in ("border_radius", "corner_radius"):
                radius = int(value)
                self._border_radius = radius
                background_updates["border_radius"] = radius
                border_geometry_changed = True
                image_size_changed = True
                layout_changed = True
            elif key == "border_width":
                self._border_width = int(value)
                border_updates["border_width"] = self._border_width
                border_geometry_changed = True
                visual_state_changed = True
                layout_changed = True
            elif key == "border_spacing":
                self._border_spacing = int(value)
                border_geometry_changed = True
                visual_state_changed = True
            elif key in ("border_color", "border_hover_color", "border_selected_color", "border_disabled_color"):
                state = {
                    "border_color": "normal",
                    "border_hover_color": "hover",
                    "border_selected_color": "selected",
                    "border_disabled_color": "disabled",
                }[key]
                if value != self._border_colors[state]:
                    self._border_colors[state] = value
                    visual_state_changed = True
            elif key in ("fg_color", "hover_color", "select_color", "disabled_color"):
                state = {
                    "fg_color": "normal",
                    "hover_color": "hover",
                    "select_color": "selected",
                    "disabled_color": "disabled",
                }[key]
                if value != self._colors[state]:
                    self._colors[state] = value
                    visual_state_changed = True
            elif key.startswith("bg_") and key.endswith("_opacity"):
                state = key.removeprefix("bg_").removesuffix("_opacity")
                opacity = float(value)
                if opacity != self._bg_opacity.get(state):
                    self._bg_opacity[state] = opacity
                    visual_state_changed = True
            elif key.startswith("button_") and key.endswith("_opacity"):
                state = key.removeprefix("button_").removesuffix("_opacity")
                opacity = float(value)
                if opacity != self._button_opacity.get(state):
                    self._button_opacity[state] = opacity
                    visual_state_changed = True
            elif key.startswith("bg_") and key.endswith("_brightness"):
                state = key.removeprefix("bg_").removesuffix("_brightness")
                brightness = float(value)
                if brightness != self._bg_brightness.get(state):
                    self._bg_brightness[state] = brightness
                    visual_state_changed = True
            elif key.startswith("button_") and key.endswith("_brightness"):
                state = key.removeprefix("button_").removesuffix("_brightness")
                brightness = float(value)
                if brightness != self._button_brightness.get(state):
                    self._button_brightness[state] = brightness
                    visual_state_changed = True
            else:
                raise ValueError(f"Unsupported Button option: {key!r}")
        if text_updates:
            self._text.configure(**text_updates)
        if self._auto_width and auto_width_changed:
            preferred_width = self._preferred_width()
            if preferred_width != self._desired_width or preferred_width != self._width:
                self._desired_width = self._width = preferred_width
                background_updates["width"] = self._width
                border_geometry_changed = True
                canvas_background_changed = True
                if self._image_size_follows_button:
                    self._image_size = (self._width, self._height)
                image_size_changed = True
                size_changed = True
        if border_geometry_changed:
            border_width, border_height, border_radius = self._border_geometry()
            border_updates.update(
                width=border_width,
                height=border_height,
                border_radius=border_radius,
            )
        if background_updates:
            self._background.configure(**background_updates)
        if border_updates and self._border_layer is not None:
            self._border_layer.configure(**border_updates)
        if image_size_changed:
            layer_width, layer_height = self._fit_image_size()
            image_updates["width"] = layer_width
            image_updates["height"] = layer_height
            image_border_radius = self._image_border_radius(layer_width, layer_height)
            image_updates["border_radius"] = image_border_radius
            image_updates["border_padding"] = 0
        if image_updates and self.image is not None:
            self._ensure_image_layer().configure(**image_updates)
        if corner_background_changed:
            self._sync_background_corners()
        if canvas_background_changed:
            self._sync_canvas_backgrounds()
        if visual_state_changed:
            self._apply_state()
        if size_changed:
            self.move(self._x, self._y)
        elif layout_changed:
            self._layout_content()
        if size_changed:
            self._notify_layout_changed()
        self._update_canvas_background_tracker()
        self._restack_layers()

    config = configure

    def cget(self, attribute_name: str) -> Any:
        values = {
            "width": self._desired_width,
            "height": self._desired_height,
            "image": self.image,
            "size": self._image_size,
            "text": self._text_value,
            "font": self._font_value,
            "command": self.command,
            "state": "disabled" if self.disabled else "normal",
            "hover": self._hover_enabled,
            "bg_color": self._bg_color,
            "text_color": self._text_color,
            "text_color_disabled": self._text_color_disabled,
            "textvariable": self._textvariable,
            "compound": self._compound,
            "background_corner_colors": self._background_corner_colors,
            "round_width_to_even_numbers": self._round_width_to_even_numbers,
            "round_height_to_even_numbers": self._round_height_to_even_numbers,
            "fg_color": self._colors["normal"],
            "hover_color": self._colors["hover"],
            "border_color": self._border_colors["normal"],
            "border_width": self._border_width,
            "border_spacing": self._border_spacing,
            "corner_radius": self._border_radius,
            "border_radius": self._border_radius,
            "anchor": self._content_anchor,
        }
        if attribute_name in values:
            return values[attribute_name]
        raise ValueError(f"Unsupported Button option: {attribute_name!r}")

    def set_text(self, text: str) -> None:
        self.configure(text=text)

    def move(self, x: int, y: int) -> None:
        self._x, self._y = int(x), int(y)
        left, top = self._winfo_origin()
        center_x = left + self._width / 2
        center_y = top + self._height / 2
        self._background.move(center_x, center_y)
        if self._image_layer is not None:
            self._image_layer.move(center_x, center_y)
        if self._border_layer is not None:
            self._border_layer.move(center_x, center_y)
        self._sync_canvas_backgrounds()
        self._layout_content()
        self._restack_layers()

    def bind(
        self,
        sequence: str | None = None,
        command: Callable | None = None,
        add: str | bool = True,
    ) -> None:
        if add not in ("+", True):
            raise ValueError("'add' argument can only be '+' or True to preserve internal callbacks")
        if self._is_lifecycle_event(sequence):
            self._bind_lifecycle_event(sequence, command, add)
            return None
        return self.canvas.tag_bind(self._event_tag, sequence, command, add="+")

    def unbind(self, sequence: str | None = None, funcid: str | None = None) -> None:
        if funcid is not None:
            raise ValueError("'funcid' argument can only be None to preserve internal callbacks")
        if self._is_lifecycle_event(sequence):
            self._unbind_lifecycle_event(sequence)
            return
        self.canvas.tag_unbind(self._event_tag, sequence)
        self._create_bindings(sequence)

    def _hide(self) -> None:
        self._pressed = False
        self._update_canvas_background_tracker()
        if self._outer_background_id is not None:
            self.canvas.itemconfigure(self._outer_background_id, state="hidden")
        for item_id in self._corner_background_ids:
            self.canvas.itemconfigure(item_id, state="hidden")

    def _show(self) -> None:
        self._sync_canvas_backgrounds()
        self._update_canvas_background_tracker()
        self._layout_content()
        self._restack_layers()

    def destroy(self) -> None:
        if self._canvas_background_tracker_registered:
            AppearanceModeTracker.remove(self._sync_canvas_backgrounds)
            self._canvas_background_tracker_registered = False
        self._set_ctk_image_source(None)
        self._detach_layout()
        self._cleanup_canvas_element()
        if self._outer_background_id is not None:
            self.canvas.delete(self._outer_background_id)
            self._outer_background_id = None
        for item_id in self._corner_background_ids:
            self.canvas.delete(item_id)
        self._corner_background_ids.clear()
