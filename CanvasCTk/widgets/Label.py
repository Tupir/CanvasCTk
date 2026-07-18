from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from typing import Any

import customtkinter as ctk
from customtkinter.windows.widgets.appearance_mode import AppearanceModeTracker
from PIL import Image as PILImage

from ..theme import get_widget_scaling
from ._shared import _appearance_color, _master_background_color, _position_canvas_text
from .Image import Image, _get_cached_resized_photo
from .Item import Item


class Label(Item):
    """Canvas-native counterpart of ``customtkinter.CTkLabel``."""

    _IMAGE_TEXT_SPACING = 2

    def __init__(
        self,
        master: Any,
        width: int = 0,
        height: int = 28,
        corner_radius: int | None = None,
        bg_color: Any = "transparent",
        fg_color: Any = None,
        text_color: Any = None,
        text_color_disabled: Any = None,
        text: str = "CTkLabel",
        font: tuple | ctk.CTkFont | None = None,
        image: Any = None,
        compound: str = "center",
        anchor: str = "center",
        wraplength: int = 0,
        justify: str = "center",
        *,
        canvas: tk.Canvas | None = None,
        x: int = 0,
        y: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, canvas=canvas, **kwargs)
        theme = ctk.ThemeManager.theme["CTkLabel"]
        self._configured_width = max(0, int(width))
        self._configured_height = max(1, int(height))
        self._requested_width = max(1, self._configured_width)
        self._requested_height = self._configured_height
        self._auto_width = True
        self._auto_height = True
        self._width = self._requested_width
        self._height = self._requested_height
        self._natural_width = self._width
        self._natural_height = self._height
        self._x, self._y = int(x), int(y)
        self._anchor = "center"

        self._corner_radius = int(theme["corner_radius"] if corner_radius is None else corner_radius)
        self._bg_color = _master_background_color(master, self.canvas) if bg_color == "transparent" else bg_color
        self._fg_color = theme["fg_color"] if fg_color is None else fg_color
        self._text_color = theme["text_color"] if text_color is None else text_color
        self._text_color_disabled = self._text_color if text_color_disabled is None else text_color_disabled
        self._track_theme_defaults(
            "CTkLabel",
            corner_radius=corner_radius is None,
            fg_color=fg_color is None,
            text_color=text_color is None,
            text_color_disabled="text_color" if text_color_disabled is None else False,
        )
        self._text = "" if text is None else str(text)
        self._font = self._coerce_font(font)
        self._image = None
        self._photo: Any = None
        self._compound = str(compound)
        self._content_anchor = str(anchor)
        self._wraplength = max(0, int(wraplength))
        self._textvariable = kwargs.pop("textvariable", None)
        self._state = str(kwargs.pop("state", "normal"))
        self._justify = str(justify)
        self._padx = int(kwargs.pop("padx", 0))
        self._pady = int(kwargs.pop("pady", 0))
        self._cursor = str(kwargs.pop("cursor", ""))
        self._takefocus = kwargs.pop("takefocus", "")
        self._underline = int(kwargs.pop("underline", -1))
        if kwargs:
            raise ValueError(f"Unsupported Label option: {next(iter(kwargs))!r}")

        self._surface: Image | None = None
        self._surface_event_required = False
        self._appearance_tracker_registered = False
        self._redraw_pending = True
        self._last_rendered_appearance: str | None = None
        physical_x, physical_y = self._physical_point(self._x, self._y)
        self._image_id = self.canvas.create_image(physical_x, physical_y, anchor="center", state="hidden")
        self._text_id = self.canvas.create_text(
            physical_x,
            physical_y,
            anchor="center",
            text=self._text,
            font=self._apply_font_scaling(self._font),
            fill=_appearance_color(self._text_color, "#ffffff"),
            justify=self._justify,
            state="hidden",
            width=self._apply_widget_scaling(self._wraplength),
        )
        self._font.add_size_configure_callback(self._font_changed)
        self._set_image(image, redraw=False)
        if self._textvariable is not None:
            self.trace_write(self._textvariable, self._variable_changed)
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

    def _font_changed(self) -> None:
        self._redraw()

    def _variable_changed(self, _: Any, value: Any) -> None:
        self._text = str(value)
        self._redraw()

    def _set_appearance_mode(self, _: str | None = None) -> None:
        if not self._is_rendered:
            self._redraw_pending = True
            return
        appearance = ctk.get_appearance_mode()
        if appearance == self._last_rendered_appearance and not self._redraw_pending:
            return
        if isinstance(self._image, ctk.CTkImage):
            self._update_image(redraw=False)
        self._redraw()

    @staticmethod
    def _has_appearance_pair(color: Any) -> bool:
        return isinstance(color, (tuple, list)) and len(color) >= 2

    def _appearance_dependent(self) -> bool:
        return isinstance(self._image, ctk.CTkImage) or any(
            self._has_appearance_pair(color)
            for color in (
                self._fg_color,
                self._text_color,
                self._text_color_disabled,
            )
        )

    def _update_appearance_tracker(self) -> None:
        needed = self._is_rendered and self._appearance_dependent()
        if needed and not self._appearance_tracker_registered:
            AppearanceModeTracker.add(self._set_appearance_mode, self.canvas)
            self._appearance_tracker_registered = True
        elif not needed and self._appearance_tracker_registered:
            AppearanceModeTracker.remove(self._set_appearance_mode)
            self._appearance_tracker_registered = False

    def _on_widget_scaling_changed(self, old_scaling: float, new_scaling: float) -> None:
        super()._on_widget_scaling_changed(old_scaling, new_scaling)
        if hasattr(self, "_image_id"):
            self._update_image(redraw=False)
            self._redraw()

    def _set_image(self, image: Any, *, redraw: bool = True) -> None:
        if isinstance(self._image, ctk.CTkImage):
            self._image.remove_configure_callback(self._update_image)
        self._image = image
        if isinstance(self._image, ctk.CTkImage):
            self._image.add_configure_callback(self._update_image)
        self._update_image(redraw=False)
        if redraw:
            self._redraw()

    def _update_image(self, *, redraw: bool = True) -> None:
        source = self._image
        if source is None:
            self._photo = None
        elif isinstance(source, ctk.CTkImage):
            self._photo = source.create_scaled_photo_image(
                get_widget_scaling(self),
                ctk.get_appearance_mode().lower(),
            )
        elif isinstance(source, PILImage.Image) or isinstance(source, (str, Path)):
            size = max(1, int(round(self._apply_widget_scaling(20))))
            self._photo = _get_cached_resized_photo(self, source, (size, size))
        else:
            self._photo = source
        self.canvas.itemconfigure(self._image_id, image=self._photo or "")
        if redraw:
            self._redraw()

    def _canvas_item_exists(self, item_id: Any) -> bool:
        try:
            return bool(self.canvas.find_withtag(item_id))
        except tk.TclError:
            return False

    def _canvas_items_alive(self) -> bool:
        return self._canvas_item_exists(getattr(self, "_image_id", None)) and self._canvas_item_exists(
            getattr(self, "_text_id", None)
        )

    def _ensure_surface(self, *, event_surface: bool = False) -> Image:
        if self._surface is not None and not self._canvas_item_exists(self._surface._image_id):
            stale_surface = self._surface
            self._surface = None
            stale_id = getattr(stale_surface, "_id", None)
            stale_surface.destroy()
            if stale_id is not None:
                self.elements.pop(stale_id, None)
            self._element_identity_keys.pop(id(stale_surface), None)
        if self._surface is None:
            self._surface = self.put(Image(
                self.master,
                canvas=self.canvas,
                width=self._width,
                height=self._height,
                x=self._x,
                y=self._y,
                anchor=self._anchor,
                fg_color=self._fg_color,
                border_radius=self._corner_radius,
                border_padding=0,
            ))
            # The image item was created after Label's content items; place it
            # immediately underneath them without lowering it below its parent.
            if self._canvas_items_alive() and self._canvas_item_exists(self._surface._image_id):
                self.canvas.tag_lower(self._surface._image_id, self._image_id)
            if self._is_rendered:
                self._surface.show()
        if event_surface:
            self._surface_event_required = True
            self._surface._enable_event_surface()
        return self._surface

    def _discard_surface_if_unused(self) -> None:
        if self._surface is None or self._surface_event_required:
            return
        if Image._color_is_visible(self._fg_color, 1):
            return
        surface = self._surface
        self._surface = None
        surface_id = getattr(surface, "_id", None)
        surface.destroy()
        if surface_id is not None:
            self.elements.pop(surface_id, None)
        self._element_identity_keys.pop(id(surface), None)

    def _image_dimensions(self) -> tuple[int, int]:
        if self._photo is None:
            return 0, 0
        try:
            width, height = int(self._photo.width()), int(self._photo.height())
        except TypeError:
            width, height = int(self._photo.width), int(self._photo.height)
        return (
            int(round(self._reverse_widget_scaling(width))),
            int(round(self._reverse_widget_scaling(height))),
        )

    def _text_dimensions(self) -> tuple[int, int]:
        if not self._text or self._compound == "none":
            return 0, 0
        self.canvas.itemconfigure(
            self._text_id,
            text=self._text,
            font=self._apply_font_scaling(self._font),
            width=self._apply_widget_scaling(self._wraplength),
            justify=self._justify,
        )
        # Tk returns no bbox for a hidden canvas text item. Labels are hidden
        # until their geometry manager renders them, but their natural size is
        # needed before that point to allocate the grid/pack cell. Temporarily
        # expose only for measurement and restore the hidden state immediately.
        was_hidden = self.canvas.itemcget(self._text_id, "state") == "hidden"
        if was_hidden:
            self.canvas.itemconfigure(self._text_id, state="normal")
        bounds = self.canvas.bbox(self._text_id)
        if was_hidden:
            self.canvas.itemconfigure(self._text_id, state="hidden")
        if bounds is None:
            return 0, 0
        return (
            int(round(self._reverse_widget_scaling(bounds[2] - bounds[0]))),
            int(round(self._reverse_widget_scaling(bounds[3] - bounds[1]))),
        )

    def _content_dimensions(self) -> tuple[int, int, int, int]:
        text_width, text_height = self._text_dimensions()
        image_width, image_height = self._image_dimensions()
        if self._compound == "none":
            text_width = text_height = 0
        elif self._compound == "text":
            image_width = image_height = 0
        spacing = self._IMAGE_TEXT_SPACING if text_width and image_width and self._compound != "center" else 0
        if self._compound in ("top", "bottom"):
            content_width = max(text_width, image_width)
            content_height = text_height + image_height + spacing
        elif self._compound in ("left", "right"):
            content_width = text_width + image_width + spacing
            content_height = max(text_height, image_height)
        else:
            content_width = max(text_width, image_width)
            content_height = max(text_height, image_height)
        return content_width, content_height, text_width, text_height

    def _fit_dimensions(
        self,
        dimensions: tuple[int, int, int, int] | None = None,
    ) -> tuple[int, int, int, int]:
        dimensions = self._content_dimensions() if dimensions is None else dimensions
        content_width, content_height, _, _ = dimensions
        minimum_height = max(1, content_height + self._pady * 2)
        natural_height = max(self._configured_height, minimum_height)
        edge_padding = min(max(0, self._corner_radius), round(natural_height / 2))
        minimum_width = max(1, content_width + (self._padx + edge_padding) * 2)
        natural_width = max(self._configured_width, minimum_width)
        self._natural_width, self._natural_height = natural_width, natural_height
        self._requested_width, self._requested_height = natural_width, natural_height
        if not self._layout_manager:
            self._width, self._height = natural_width, natural_height
        return dimensions

    def _content_center(self, content_width: int, content_height: int) -> tuple[float, float]:
        left, top = self._winfo_origin()
        right, bottom = left + self._width, top + self._height
        anchor = self._content_anchor.lower()
        edge_padding = min(max(0, self._corner_radius), round(self._height / 2))
        if anchor in {"w", "nw", "sw"}:
            center_x = left + edge_padding + self._padx + content_width / 2
        elif anchor in {"e", "ne", "se"}:
            center_x = right - edge_padding - self._padx - content_width / 2
        else:
            center_x = (left + right) / 2
        if anchor in {"n", "ne", "nw"}:
            center_y = top + self._pady + content_height / 2
        elif anchor in {"s", "se", "sw"}:
            center_y = bottom - self._pady - content_height / 2
        else:
            center_y = (top + bottom) / 2
        return center_x, center_y

    def _redraw_content(
        self,
        dimensions: tuple[int, int, int, int] | None = None,
    ) -> None:
        dimensions = self._content_dimensions() if dimensions is None else dimensions
        content_width, content_height, text_width, text_height = dimensions
        image_width, image_height = self._image_dimensions()
        center_x, center_y = self._content_center(content_width, content_height)
        text_x = image_x = center_x
        text_y = image_y = center_y
        spacing = self._IMAGE_TEXT_SPACING if text_width and image_width else 0
        if text_width and image_width:
            if self._compound == "left":
                image_x = center_x - (text_width + spacing) / 2
                text_x = center_x + (image_width + spacing) / 2
            elif self._compound == "right":
                text_x = center_x - (image_width + spacing) / 2
                image_x = center_x + (text_width + spacing) / 2
            elif self._compound == "top":
                image_y = center_y - (text_height + spacing) / 2
                text_y = center_y + (image_height + spacing) / 2
            elif self._compound == "bottom":
                text_y = center_y - (image_height + spacing) / 2
                image_y = center_y + (text_height + spacing) / 2
        physical_text_x, physical_text_y = self._physical_point(text_x, text_y)
        physical_image_x, physical_image_y = self._physical_point(image_x, image_y)
        _position_canvas_text(self.canvas, self._text_id, physical_text_x, physical_text_y, "center")
        self.canvas.coords(self._image_id, physical_image_x, physical_image_y)
        show_text = bool(self._text) and self._compound != "none" and self._is_rendered
        show_image = self._photo is not None and self._compound != "text" and self._is_rendered
        self.canvas.itemconfigure(self._text_id, state="normal" if show_text else "hidden")
        self.canvas.itemconfigure(self._image_id, state="normal" if show_image else "hidden")

    def _redraw(self) -> None:
        if self._destroyed or not self._canvas_items_alive():
            self._is_rendered = False
            return
        old_request = self._natural_width, self._natural_height
        dimensions = self._fit_dimensions()
        if not self._is_rendered:
            self._redraw_pending = True
            if old_request != (self._natural_width, self._natural_height):
                if self._canvas_host is not None:
                    self._canvas_host._schedule_child_layout()
                elif self._layout_manager:
                    self._schedule_canvas_layout()
            return
        if Image._color_is_visible(self._fg_color, 1) or self._surface_event_required:
            self._ensure_surface(event_surface=self._surface_event_required).configure(
                width=self._width,
                height=self._height,
                anchor=self._anchor,
                fg_color=self._fg_color,
                border_radius=min(self._corner_radius, self._height // 2),
                border_padding=0,
            )
        else:
            self._discard_surface_if_unused()
        color = self._text_color_disabled if self._state == tk.DISABLED else self._text_color
        self.canvas.itemconfigure(self._text_id, fill=_appearance_color(color, "#ffffff"))
        self._redraw_content(dimensions)
        self._redraw_pending = False
        self._last_rendered_appearance = ctk.get_appearance_mode()
        if old_request != (self._natural_width, self._natural_height):
            if self._canvas_host is not None:
                self._canvas_host._schedule_child_layout()
            elif self._layout_manager:
                self._schedule_canvas_layout()

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        changed = bool(require_redraw)
        for key, value in kwargs.items():
            if key == "width":
                value = max(0, int(value))
                if value == self._configured_width:
                    continue
                self._configured_width = value
            elif key == "height":
                value = max(1, int(value))
                if value == self._configured_height:
                    continue
                self._configured_height = value
            elif key == "corner_radius":
                value = int(value)
                if value == self._corner_radius:
                    continue
                self._corner_radius = value
            elif key == "bg_color":
                value = (
                    _master_background_color(self.master, self.canvas)
                    if value == "transparent"
                    else value
                )
                if value == self._bg_color:
                    continue
                self._bg_color = value
            elif key == "fg_color":
                if value == self._fg_color:
                    continue
                self._fg_color = value
            elif key == "text_color":
                if value == self._text_color:
                    continue
                self._text_color = value
            elif key == "text_color_disabled":
                if value == self._text_color_disabled:
                    continue
                self._text_color_disabled = value
            elif key == "text":
                value = "" if value is None else str(value)
                if value == self._text:
                    continue
                self._text = value
            elif key == "font":
                if value is self._font:
                    continue
                self._font.remove_size_configure_callback(self._font_changed)
                self._font = self._coerce_font(value)
                self._font.add_size_configure_callback(self._font_changed)
            elif key == "image":
                if value is self._image or value == self._image:
                    continue
                self._set_image(value, redraw=False)
            elif key == "compound":
                value = str(value)
                if value == self._compound:
                    continue
                self._compound = value
            elif key == "anchor":
                value = str(value)
                if value == self._content_anchor:
                    continue
                self._content_anchor = value
            elif key == "wraplength":
                value = max(0, int(value))
                if value == self._wraplength:
                    continue
                self._wraplength = value
            elif key == "textvariable":
                if value is self._textvariable:
                    continue
                self.untrace_write()
                self._textvariable = value
                if value is not None:
                    self.trace_write(value, self._variable_changed)
            elif key == "state":
                value = str(value)
                if value == self._state:
                    continue
                self._state = value
            elif key == "justify":
                value = str(value)
                if value == self._justify:
                    continue
                self._justify = value
            elif key == "padx":
                value = int(value)
                if value == self._padx:
                    continue
                self._padx = value
            elif key == "pady":
                value = int(value)
                if value == self._pady:
                    continue
                self._pady = value
            elif key == "cursor":
                value = str(value)
                if value == self._cursor:
                    continue
                self._cursor = value
            elif key == "takefocus":
                if value == self._takefocus:
                    continue
                self._takefocus = value
            elif key == "underline":
                value = int(value)
                if value == self._underline:
                    continue
                self._underline = value
            else:
                raise ValueError(f"Unsupported Label option: {key!r}")
            changed = True
        self._update_appearance_tracker()
        if changed:
            self._redraw()

    config = configure

    def cget(self, attribute_name: str) -> Any:
        values = {
            "width": self._configured_width,
            "height": self._configured_height,
            "corner_radius": self._corner_radius,
            "bg_color": self._bg_color,
            "fg_color": self._fg_color,
            "text_color": self._text_color,
            "text_color_disabled": self._text_color_disabled,
            "text": self._text,
            "font": self._font,
            "image": self._image,
            "compound": self._compound,
            "anchor": self._content_anchor,
            "wraplength": self._wraplength,
            "textvariable": self._textvariable,
            "state": self._state,
            "justify": self._justify,
            "padx": self._padx,
            "pady": self._pady,
            "cursor": self._cursor,
            "takefocus": self._takefocus,
            "underline": self._underline,
        }
        if attribute_name not in values:
            raise ValueError(f"Unsupported Label option: {attribute_name!r}")
        return values[attribute_name]

    def set(self, value: str) -> None:
        self.configure(text=value)

    def _set_anchor(self, anchor: str) -> None:
        self._anchor = str(anchor)
        if self._surface is not None:
            self._surface.configure(anchor=self._anchor)

    def _apply_geometry_allocation(
        self,
        width: int | None,
        height: int | None,
    ) -> None:
        target_width = self._natural_width if width is None else max(1, int(width))
        target_height = self._natural_height if height is None else max(1, int(height))
        if (target_width, target_height) == (self._width, self._height):
            return
        self._width, self._height = target_width, target_height
        self._redraw()

    def _resize_for_place(self, width: int | None, height: int | None) -> None:
        self._apply_geometry_allocation(width, height)

    def winfo_reqwidth(self) -> int:
        return max(1, int(round(self._apply_widget_scaling(self._natural_width))))

    def winfo_reqheight(self) -> int:
        return max(1, int(round(self._apply_widget_scaling(self._natural_height))))

    def move(self, x: int, y: int) -> None:
        self._x, self._y = int(x), int(y)
        if self._surface is not None:
            self._surface.move(self._x, self._y)
        self._redraw_content()

    def bind(self, sequence: str | None = None, command: Callable | None = None, add: str | bool = True) -> Any:
        if self._is_lifecycle_event(sequence):
            return self._bind_lifecycle_event(sequence, command, add)
        if add not in ("+", True):
            raise ValueError("'add' argument can only be '+' or True")
        result = None
        surface = self._ensure_surface(event_surface=True)
        if not self._canvas_items_alive():
            return None
        self.canvas.tag_lower(surface._image_id, self._image_id)
        for target in (surface._image_id, self._image_id, self._text_id):
            result = self.canvas.tag_bind(target, sequence, command, add="+")
        return result

    def unbind(self, sequence: str | None = None, funcid: str | None = None) -> None:
        if self._is_lifecycle_event(sequence):
            self._unbind_lifecycle_event(sequence, funcid)
            return
        if funcid is not None:
            raise ValueError("'funcid' must be None")
        targets = [self._image_id, self._text_id]
        if self._surface is not None:
            targets.insert(0, self._surface._image_id)
        for target in targets:
            self.canvas.tag_unbind(target, sequence)

    def focus(self) -> Any:
        return self.canvas.focus(self._text_id)

    focus_set = focus
    focus_force = focus

    def _hide(self) -> None:
        self._update_appearance_tracker()
        self.canvas.itemconfigure(self._text_id, state="hidden")
        self.canvas.itemconfigure(self._image_id, state="hidden")

    def _show(self) -> None:
        self._update_appearance_tracker()
        if self._redraw_pending or (
            self._appearance_dependent()
            and ctk.get_appearance_mode() != self._last_rendered_appearance
        ):
            self._set_appearance_mode()
        else:
            self._redraw_content()

    def destroy(self) -> None:
        if self._appearance_tracker_registered:
            AppearanceModeTracker.remove(self._set_appearance_mode)
            self._appearance_tracker_registered = False
        self._font.remove_size_configure_callback(self._font_changed)
        if isinstance(self._image, ctk.CTkImage):
            self._image.remove_configure_callback(self._update_image)
        self._detach_layout()
        self._cleanup_canvas_element()
        self.canvas.delete(self._image_id)
        self.canvas.delete(self._text_id)
        self._photo = None


__all__ = ["Label"]
