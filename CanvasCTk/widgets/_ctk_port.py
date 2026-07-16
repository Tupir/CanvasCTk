from __future__ import annotations

from copy import copy
from typing import Any, Callable

import customtkinter as ctk
from customtkinter.windows.widgets.appearance_mode import AppearanceModeTracker
from customtkinter.windows.widgets.core_rendering import DrawEngine

from .Item import Item
from ._shared import _master_background_color


class CanvasDrawProxy:
    """Give CustomTkinter's draw engine a local, namespaced view of a shared canvas."""

    def __init__(
        self,
        owner: "CanvasCTkWidget",
        *,
        tag_suffix: str = "",
        origin_offset: tuple[int | float, int | float] = (0, 0),
        physical_coordinates: bool = False,
    ) -> None:
        self._owner = owner
        self._canvas = owner.canvas
        self._tag_suffix = tag_suffix
        self._owner_root_tag = f"canvasctk_port_{id(owner)}"
        self._root_tag = f"{self._owner_root_tag}{':' + tag_suffix if tag_suffix else ''}"
        self._origin_offset = origin_offset
        self._physical_coordinates = bool(physical_coordinates)

    def _origin(self) -> tuple[int, int]:
        x, y = self._owner._winfo_origin()
        return self._owner._physical_point(
            x + self._origin_offset[0],
            y + self._origin_offset[1],
        )

    def scoped(self, tag_suffix: str, x: int | float = 0, y: int | float = 0) -> "CanvasDrawProxy":
        return CanvasDrawProxy(
            self._owner,
            tag_suffix=tag_suffix,
            origin_offset=(self._origin_offset[0] + x, self._origin_offset[1] + y),
            physical_coordinates=self._physical_coordinates,
        )

    def physical(self) -> "CanvasDrawProxy":
        """Return the same scoped canvas view using physical pixel coordinates."""
        return CanvasDrawProxy(
            self._owner,
            tag_suffix=self._tag_suffix,
            origin_offset=self._origin_offset,
            physical_coordinates=True,
        )

    def _tag(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._root_tag if value == "all" else f"{self._root_tag}:{value}"
        if isinstance(value, (tuple, list)):
            return tuple(self._tag(item) for item in value)
        return value

    def _unprefix_tag(self, value: str) -> str:
        prefix = f"{self._root_tag}:"
        return value[len(prefix):] if value.startswith(prefix) else value

    @staticmethod
    def _shift_pairs(values: list[Any], x_offset: int, y_offset: int) -> list[Any]:
        shifted = list(values)
        for index in range(0, len(shifted) - 1, 2):
            if isinstance(shifted[index], (int, float)) and isinstance(shifted[index + 1], (int, float)):
                shifted[index] += x_offset
                shifted[index + 1] += y_offset
        return shifted

    @staticmethod
    def _unshift_pairs(values: list[Any], x_offset: int, y_offset: int) -> list[Any]:
        return CanvasDrawProxy._shift_pairs(values, -x_offset, -y_offset)

    def _scale_pairs(self, values: list[Any]) -> list[Any]:
        if self._physical_coordinates:
            return list(values)
        scaled = list(values)
        for index in range(0, len(scaled) - 1, 2):
            if isinstance(scaled[index], (int, float)) and isinstance(scaled[index + 1], (int, float)):
                scaled[index] = self._owner._apply_widget_scaling(scaled[index])
                scaled[index + 1] = self._owner._apply_widget_scaling(scaled[index + 1])
        return scaled

    def _unscale_pairs(self, values: list[Any]) -> list[Any]:
        if self._physical_coordinates:
            return list(values)
        unscaled = list(values)
        for index in range(0, len(unscaled) - 1, 2):
            if isinstance(unscaled[index], (int, float)) and isinstance(unscaled[index + 1], (int, float)):
                unscaled[index] = self._owner._reverse_widget_scaling(unscaled[index])
                unscaled[index + 1] = self._owner._reverse_widget_scaling(unscaled[index + 1])
        return unscaled

    def _scale_options(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        options = dict(kwargs)
        if self._physical_coordinates:
            return options
        if "font" in options:
            options["font"] = self._owner._apply_font_scaling(options["font"])
        if isinstance(options.get("width"), (int, float)):
            options["width"] = self._owner._apply_widget_scaling(options["width"])
        return options

    def _shift_create_arguments(self, args: tuple[Any, ...]) -> tuple[Any, ...]:
        x_offset, y_offset = self._origin()
        if len(args) == 1 and isinstance(args[0], (tuple, list)):
            return (self._shift_pairs(self._scale_pairs(list(args[0])), x_offset, y_offset),)
        return tuple(self._shift_pairs(self._scale_pairs(list(args)), x_offset, y_offset))

    def _create(self, name: str, *args: Any, **kwargs: Any) -> int:
        owner_tags = () if self._root_tag == self._owner_root_tag else (self._owner_root_tag,)
        if "tags" in kwargs:
            tags = kwargs["tags"]
            if isinstance(tags, (tuple, list)):
                kwargs["tags"] = (*self._tag(tags), self._root_tag, *owner_tags)
            elif tags:
                kwargs["tags"] = (self._tag(tags), self._root_tag, *owner_tags)
            else:
                kwargs["tags"] = (self._root_tag, *owner_tags)
        else:
            kwargs["tags"] = (self._root_tag, *owner_tags)
        if not self._owner._is_rendered:
            kwargs["state"] = "hidden"
        return getattr(self._canvas, name)(*self._shift_create_arguments(args), **self._scale_options(kwargs))

    def create_polygon(self, *args: Any, **kwargs: Any) -> int:
        return self._create("create_polygon", *args, **kwargs)

    def create_rectangle(self, *args: Any, **kwargs: Any) -> int:
        return self._create("create_rectangle", *args, **kwargs)

    def create_oval(self, *args: Any, **kwargs: Any) -> int:
        return self._create("create_oval", *args, **kwargs)

    def create_line(self, *args: Any, **kwargs: Any) -> int:
        return self._create("create_line", *args, **kwargs)

    def create_text(self, *args: Any, **kwargs: Any) -> int:
        return self._create("create_text", *args, **kwargs)

    def create_aa_circle(self, x_pos: int, y_pos: int, radius: int, *args: Any, **kwargs: Any) -> int:
        x_offset, y_offset = self._origin()
        owner_tags = () if self._root_tag == self._owner_root_tag else (self._owner_root_tag,)
        if "tags" in kwargs:
            tags = kwargs["tags"]
            kwargs["tags"] = (
                (*self._tag(tags), self._root_tag, *owner_tags)
                if isinstance(tags, (tuple, list))
                else (self._tag(tags), self._root_tag, *owner_tags)
            )
        else:
            kwargs["tags"] = (self._root_tag, *owner_tags)
        scaled_x = x_pos if self._physical_coordinates else self._owner._apply_widget_scaling(x_pos)
        scaled_y = y_pos if self._physical_coordinates else self._owner._apply_widget_scaling(y_pos)
        scaled_radius = radius if self._physical_coordinates else self._owner._apply_widget_scaling(radius)
        item_id = self._canvas.create_aa_circle(
            scaled_x + x_offset,
            scaled_y + y_offset,
            max(0, int(round(scaled_radius))),
            *args,
            **kwargs,
        )
        if not self._owner._is_rendered:
            self._canvas.itemconfigure(item_id, state="hidden")
        return item_id

    def coords(self, tag_or_id: Any, *args: Any) -> Any:
        target = self._tag(tag_or_id)
        if not args:
            values = list(self._canvas.coords(target))
            x_offset, y_offset = self._origin()
            return self._unscale_pairs(self._unshift_pairs(values, x_offset, y_offset))

        x_offset, y_offset = self._origin()
        values = list(args[0]) if len(args) == 1 and isinstance(args[0], (tuple, list)) else list(args)
        tags = self._canvas.gettags(target) if not isinstance(target, int) else self._canvas.gettags(target)
        is_aa_circle = "ctk_aa_circle_font_element" in tags
        if is_aa_circle:
            shifted = list(values)
            if len(shifted) >= 2:
                if self._physical_coordinates:
                    shifted[0] += x_offset
                    shifted[1] += y_offset
                else:
                    shifted[0] = int(round(self._owner._apply_widget_scaling(shifted[0]) + x_offset))
                    shifted[1] = int(round(self._owner._apply_widget_scaling(shifted[1]) + y_offset))
            if len(shifted) == 3 and isinstance(shifted[2], (int, float)):
                # CTkCanvas uses the radius as an exact dictionary key for its
                # antialiased shape glyph.  CTk's scaling can produce values
                # such as 4.800000000000001, so keep the proxy's update path
                # consistent with create_aa_circle() and pass an integer.
                radius = shifted[2] if self._physical_coordinates else self._owner._apply_widget_scaling(shifted[2])
                shifted[2] = max(0, int(round(radius)))
        else:
            shifted = self._shift_pairs(self._scale_pairs(values), x_offset, y_offset)
        return self._canvas.coords(target, *shifted)

    def itemconfig(self, tag_or_id: Any, *args: Any, **kwargs: Any) -> Any:
        if not self._owner._is_rendered and "state" in kwargs:
            kwargs["state"] = "hidden"
        return self._canvas.itemconfig(self._tag(tag_or_id), *args, **self._scale_options(kwargs))

    itemconfigure = itemconfig

    def delete(self, tag_or_id: Any) -> Any:
        return self._canvas.delete(self._tag(tag_or_id))

    def find_withtag(self, tag_or_id: Any) -> Any:
        matches = self._canvas.find_withtag(self._tag(tag_or_id))
        if matches or not isinstance(tag_or_id, str):
            return matches

        # DrawEngine's vertical split checks these unsuffixed tags, but creates
        # left/right variants. Resolve the check to either existing half so a
        # redraw does not leave duplicate 3x3 rectangles at the widget origin.
        split_aliases = {
            "inner_rectangle_1": "inner_rectangle_left_1",
            "inner_rectangle_2": "inner_rectangle_left_2",
        }
        alias = split_aliases.get(tag_or_id)
        return () if alias is None else self._canvas.find_withtag(self._tag(alias))

    def gettags(self, tag_or_id: Any) -> tuple[str, ...]:
        return tuple(self._unprefix_tag(tag) for tag in self._canvas.gettags(self._tag(tag_or_id)))

    def addtag_withtag(self, newtag: str, tag_or_id: Any) -> Any:
        return self._canvas.addtag_withtag(self._tag(newtag), self._tag(tag_or_id))

    def tag_lower(self, tag_or_id: Any, below_this: Any | None = None) -> Any:
        if below_this is None:
            # CTk's DrawEngine assumes a private canvas. On CanvasCTk's shared
            # canvas, lowering without a sibling would put the widget beneath
            # its parent Frame background, making the control disappear.
            return None
        return self._canvas.tag_lower(self._tag(tag_or_id), self._tag(below_this))

    def tag_raise(self, tag_or_id: Any, above_this: Any | None = None) -> Any:
        if above_this is None:
            return None
        return self._canvas.tag_raise(self._tag(tag_or_id), self._tag(above_this))

    def _event_callback(self, callback: Callable[..., Any]) -> Callable[[Any], Any]:
        def dispatch(event: Any) -> Any:
            local_event = copy(event)
            x_offset, y_offset = self._origin()
            if hasattr(local_event, "x"):
                local_event.x = self._owner._reverse_widget_scaling(local_event.x - x_offset)
            if hasattr(local_event, "y"):
                local_event.y = self._owner._reverse_widget_scaling(local_event.y - y_offset)
            return callback(local_event)
        return dispatch

    def bind(self, sequence: str | None = None, command: Callable[..., Any] | None = None, add: Any = None) -> Any:
        if command is None:
            return self._canvas.tag_bind(self._root_tag, sequence)
        return self._canvas.tag_bind(self._root_tag, sequence, self._event_callback(command), add=add)

    def unbind(self, sequence: str | None = None, funcid: str | None = None) -> Any:
        return self._canvas.tag_unbind(self._root_tag, sequence, funcid)

    def tag_bind(self, tag_or_id: Any, sequence: str | None = None, command: Callable[..., Any] | None = None, add: Any = None) -> Any:
        if command is None:
            return self._canvas.tag_bind(self._tag(tag_or_id), sequence)
        return self._canvas.tag_bind(self._tag(tag_or_id), sequence, self._event_callback(command), add=add)

    def tag_unbind(self, tag_or_id: Any, sequence: str | None = None, funcid: str | None = None) -> Any:
        return self._canvas.tag_unbind(self._tag(tag_or_id), sequence, funcid)

    def configure(self, **kwargs: Any) -> None:
        cursor = kwargs.get("cursor")
        if cursor is not None:
            self._canvas.configure(cursor=cursor)

    config = configure

    def focus(self, *args: Any) -> Any:
        return self._canvas.focus(*args)

    def focus_set(self) -> Any:
        return self._canvas.focus_set()

    def focus_force(self) -> Any:
        return self._canvas.focus_force()

    def hide_all(self) -> None:
        self._canvas.itemconfigure(self._root_tag, state="hidden")

    def show_all(self) -> None:
        self._canvas.itemconfigure(
            self._root_tag,
            state="normal" if self._owner._is_rendered else "hidden",
        )

    def destroy_all(self) -> None:
        self._canvas.delete(self._root_tag)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._canvas, name)


class CanvasDrawEngine(DrawEngine):
    """Run CustomTkinter's shape rounding in physical pixels, like native CTk."""

    def __init__(self, owner: "CanvasCTkWidget", canvas: CanvasDrawProxy) -> None:
        self._owner = owner
        super().__init__(canvas.physical())

    def _scale(self, value: int | float) -> float:
        return self._owner._apply_widget_scaling(value)

    def draw_background_corners(self, width: int | float, height: int | float) -> bool:
        return super().draw_background_corners(self._scale(width), self._scale(height))

    def draw_rounded_rect_with_border(
        self,
        width: int | float,
        height: int | float,
        corner_radius: int | float,
        border_width: int | float,
        overwrite_preferred_drawing_method: str | None = None,
    ) -> bool:
        return super().draw_rounded_rect_with_border(
            self._scale(width),
            self._scale(height),
            self._scale(corner_radius),
            self._scale(border_width),
            overwrite_preferred_drawing_method,
        )

    def draw_rounded_rect_with_border_vertical_split(
        self,
        width: int | float,
        height: int | float,
        corner_radius: int | float,
        border_width: int | float,
        left_section_width: int | float,
    ) -> bool:
        return super().draw_rounded_rect_with_border_vertical_split(
            self._scale(width),
            self._scale(height),
            self._scale(corner_radius),
            self._scale(border_width),
            self._scale(left_section_width),
        )

    def draw_rounded_progress_bar_with_border(
        self,
        width: int | float,
        height: int | float,
        corner_radius: int | float,
        border_width: int | float,
        progress_value_1: float,
        progress_value_2: float,
        orientation: str,
    ) -> bool:
        return super().draw_rounded_progress_bar_with_border(
            self._scale(width),
            self._scale(height),
            self._scale(corner_radius),
            self._scale(border_width),
            progress_value_1,
            progress_value_2,
            orientation,
        )

    def draw_rounded_slider_with_border_and_button(
        self,
        width: int | float,
        height: int | float,
        corner_radius: int | float,
        border_width: int | float,
        button_length: int | float,
        button_corner_radius: int | float,
        slider_value: float,
        orientation: str,
    ) -> bool:
        return super().draw_rounded_slider_with_border_and_button(
            self._scale(width),
            self._scale(height),
            self._scale(corner_radius),
            self._scale(border_width),
            self._scale(button_length),
            self._scale(button_corner_radius),
            slider_value,
            orientation,
        )

    def draw_rounded_scrollbar(
        self,
        width: int | float,
        height: int | float,
        corner_radius: int | float,
        border_spacing: int | float,
        start_value: float,
        end_value: float,
        orientation: str,
    ) -> bool:
        return super().draw_rounded_scrollbar(
            self._scale(width),
            self._scale(height),
            self._scale(corner_radius),
            self._scale(border_spacing),
            start_value,
            end_value,
            orientation,
        )

    def draw_checkmark(self, width: int | float, height: int | float, size: int | float) -> bool:
        return super().draw_checkmark(self._scale(width), self._scale(height), self._scale(size))

    def draw_dropdown_arrow(
        self,
        x_position: int | float,
        y_position: int | float,
        size: int | float,
    ) -> bool:
        return super().draw_dropdown_arrow(
            self._scale(x_position),
            self._scale(y_position),
            self._scale(size),
        )


class  CanvasCTkWidget(Item):
    """CanvasCTk base for widgets ported directly from CustomTkinter draw logic."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Coalesce repeated DrawEngine calls while an initialized widget is hidden."""
        super().__init_subclass__(**kwargs)
        draw = cls.__dict__.get("_draw")
        if draw is None or getattr(draw, "_canvasctk_deferred_wrapper", False):
            return

        def deferred_draw(self: "CanvasCTkWidget", *args: Any, **draw_kwargs: Any) -> Any:
            if not getattr(self, "_is_rendered", False):
                self._draw_pending = True
                return None
            result = draw(self, *args, **draw_kwargs)
            self._draw_initialized = True
            self._draw_pending = False
            return result

        deferred_draw._canvasctk_deferred_wrapper = True  # type: ignore[attr-defined]
        deferred_draw.__name__ = draw.__name__
        deferred_draw.__doc__ = draw.__doc__
        setattr(cls, "_draw", deferred_draw)

    def __init__(
        self,
        master: Any,
        *,
        width: int,
        height: int,
        bg_color: Any = "transparent",
        canvas: Any = None,
        x: int = 0,
        y: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, canvas=canvas, **kwargs)
        self._desired_width = max(1, int(width))
        self._desired_height = max(1, int(height))
        self._current_width = self._desired_width
        self._current_height = self._desired_height
        self._width = self._current_width
        self._height = self._current_height
        self._x = int(x)
        self._y = int(y)
        self._anchor = "center"
        checked_bg_color = self._check_color_type(bg_color, transparency=True)
        self._bg_color = (
            _master_background_color(master, self.canvas)
            if checked_bg_color == "transparent"
            else checked_bg_color
        )
        self._cursor_manipulation_enabled = True
        self._cursor = ""
        self._appearance_mode = 1 if ctk.get_appearance_mode() == "Dark" else 0
        self._appearance_callback_registered = False
        self._draw_initialized = False
        self._draw_pending = False
        self._suspend_dimension_draw = False
        self._canvas = CanvasDrawProxy(self)
        self._draw_engine = CanvasDrawEngine(self, self._canvas)

    def _uses_appearance_dependent_values(self) -> bool:
        for name, value in vars(self).items():
            if "color" not in name and "image" not in name:
                continue
            if (
                isinstance(value, (tuple, list))
                and len(value) == 2
                and all(isinstance(part, str) for part in value)
            ):
                return True
            if isinstance(value, ctk.CTkImage):
                return True
        return False

    def _sync_appearance_callback(self) -> None:
        needs_callback = self._is_rendered and self._uses_appearance_dependent_values()
        if needs_callback and not self._appearance_callback_registered:
            AppearanceModeTracker.add(self._set_appearance_mode, self.canvas)
            self._appearance_callback_registered = True
        elif not needs_callback and self._appearance_callback_registered:
            AppearanceModeTracker.remove(self._set_appearance_mode)
            self._appearance_callback_registered = False

    @staticmethod
    def _check_color_type(color: Any, transparency: bool = False) -> Any:
        if color is None:
            raise ValueError("color is None, for transparency set color='transparent'")
        if isinstance(color, (tuple, list)) and (
            color[0] == "transparent" or color[1] == "transparent"
        ):
            raise ValueError(f"transparency is not allowed in tuple color {color}, use 'transparent'")
        if color == "transparent" and not transparency:
            raise ValueError("transparency is not allowed for this attribute")
        if isinstance(color, str):
            return color
        if (
            isinstance(color, (tuple, list))
            and len(color) == 2
            and isinstance(color[0], str)
            and isinstance(color[1], str)
        ):
            return color
        raise ValueError(
            f"color {color} must be string ('transparent' or 'color-name' or 'hex-color') "
            f"or tuple of two strings, not {type(color)}"
        )

    def _apply_appearance_mode(self, color: Any) -> Any:
        if color == "transparent":
            return ""
        if isinstance(color, (tuple, list)):
            return color[min(self._appearance_mode, len(color) - 1)]
        return color

    def _set_appearance_mode(self, mode_string: str) -> None:
        appearance_mode = 1 if mode_string == "Dark" else 0
        if appearance_mode == self._appearance_mode:
            return
        self._appearance_mode = appearance_mode
        draw = getattr(self, "_draw", None)
        if draw is not None and self._is_rendered:
            draw()
        elif draw is not None:
            self._draw_pending = True

    def _set_dimensions(self, width: int | None = None, height: int | None = None) -> bool:
        changed = False
        if width is not None:
            target_width = max(1, int(width))
            if target_width != self._current_width:
                self._desired_width = self._current_width = self._width = target_width
                changed = True
        if height is not None:
            target_height = max(1, int(height))
            if target_height != self._current_height:
                self._desired_height = self._current_height = self._height = target_height
                changed = True
        draw = getattr(self, "_draw", None)
        if changed and draw is not None and not self._suspend_dimension_draw:
            draw()
        return changed

    def _on_widget_scaling_changed(self, old_scaling: float, new_scaling: float) -> None:
        super()._on_widget_scaling_changed(old_scaling, new_scaling)
        draw = getattr(self, "_draw", None)
        if draw is not None and hasattr(self, "_canvas"):
            draw()

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        width = kwargs.pop("width", None)
        height = kwargs.pop("height", None)
        if width is not None or height is not None:
            self._suspend_dimension_draw = True
            try:
                require_redraw = self._set_dimensions(width=width, height=height) or require_redraw
            finally:
                self._suspend_dimension_draw = False
        if "bg_color" in kwargs:
            checked_bg_color = self._check_color_type(kwargs.pop("bg_color"), transparency=True)
            resolved_bg_color = (
                _master_background_color(self.master, self.canvas)
                if checked_bg_color == "transparent"
                else checked_bg_color
            )
            if resolved_bg_color != self._bg_color:
                self._bg_color = resolved_bg_color
                require_redraw = True
        if "cursor" in kwargs:
            cursor = str(kwargs.pop("cursor") or "")
            if cursor != self._cursor:
                self._cursor = cursor
                self.canvas.configure(cursor=cursor)
        if kwargs:
            unknown = next(iter(kwargs))
            raise ValueError(f"Unsupported {self.__class__.__name__} option: {unknown!r}")
        if require_redraw:
            self._draw()
        self._sync_appearance_callback()

    config = configure

    def cget(self, attribute_name: str) -> Any:
        values = {
            "width": self._desired_width,
            "height": self._desired_height,
            "bg_color": self._bg_color,
            "cursor": self._cursor,
        }
        if attribute_name not in values:
            raise ValueError(f"Unsupported {self.__class__.__name__} option: {attribute_name!r}")
        return values[attribute_name]

    def _set_anchor(self, anchor: str) -> None:
        anchor = str(anchor)
        if anchor == self._anchor:
            return
        old_left, old_top = self._winfo_origin()
        self._anchor = anchor
        new_left, new_top = self._winfo_origin()
        delta_x, delta_y = self._physical_point(new_left - old_left, new_top - old_top)
        if delta_x or delta_y:
            self.canvas.move(self._canvas._owner_root_tag, delta_x, delta_y)

    def _resize_for_place(self, width: int | None, height: int | None) -> None:
        # Geometry managers control the current allocation, not the widget's
        # configured/requested size.  When fill/sticky/relative sizing is
        # removed, restore the CTk desired dimensions.
        target_width = self._desired_width if width is None else max(1, int(width))
        target_height = self._desired_height if height is None else max(1, int(height))
        changed = False
        if target_width != self._current_width:
            self._current_width = self._width = target_width
            changed = True
        if target_height != self._current_height:
            self._current_height = self._height = target_height
            changed = True
        draw = getattr(self, "_draw", None)
        if changed and draw is not None:
            draw()

    def move(self, x: int, y: int) -> None:
        x, y = int(x), int(y)
        if x == self._x and y == self._y:
            return
        old_left, old_top = self._winfo_origin()
        self._x, self._y = x, y
        new_left, new_top = self._winfo_origin()
        delta_x, delta_y = self._physical_point(new_left - old_left, new_top - old_top)
        if delta_x or delta_y:
            # Every DrawEngine item, including scoped sub-canvases, carries
            # the owner tag. Moving that tag is equivalent to recomputing
            # thousands of coordinates but costs a single Tcl command.
            self.canvas.move(self._canvas._owner_root_tag, delta_x, delta_y)

    def bind(self, sequence: str | None = None, command: Callable[..., Any] | None = None, add: Any = True) -> Any:
        if self._is_lifecycle_event(sequence):
            return self._bind_lifecycle_event(sequence, command, add)
        if add not in ("+", True, None):
            raise ValueError("'add' argument can only be '+' or True")
        return self._canvas.bind(sequence, command, add=add)

    def unbind(self, sequence: str | None = None, funcid: str | None = None) -> Any:
        if self._is_lifecycle_event(sequence):
            return self._unbind_lifecycle_event(sequence, funcid)
        result = self._canvas.unbind(sequence, funcid)
        create_bindings = getattr(self, "_create_bindings", None)
        if funcid is None and callable(create_bindings):
            create_bindings(sequence)
        return result

    def focus(self) -> Any:
        return self._canvas.focus()

    focus_set = focus
    focus_force = focus

    def _hide(self) -> None:
        self._sync_appearance_callback()
        self._canvas.hide_all()

    def _show(self) -> None:
        current_mode = 1 if ctk.get_appearance_mode() == "Dark" else 0
        appearance_changed = current_mode != self._appearance_mode
        self._appearance_mode = current_mode
        if self._draw_pending or (appearance_changed and self._uses_appearance_dependent_values()):
            self._draw_pending = False
            self._draw()
        self._canvas.show_all()
        self._sync_appearance_callback()

    def destroy(self) -> None:
        if self._appearance_callback_registered:
            AppearanceModeTracker.remove(self._set_appearance_mode)
            self._appearance_callback_registered = False
        self.untrace_write()
        self._detach_layout()
        self._canvas.destroy_all()
        self._cleanup_canvas_element()


__all__ = ["CanvasCTkWidget", "CanvasDrawProxy", "CanvasDrawEngine"]
