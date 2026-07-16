from __future__ import annotations

import tkinter as tk
from heapq import heappop, heappush

from pathlib import Path
from typing import Any

import customtkinter as ctk
from customtkinter.windows.widgets.appearance_mode import AppearanceModeTracker

from ._identity_registry import IdentityRegistry
from .element import Element, ElementBase
from .widgets import Button, Image, Item, Label, Scrollbar, SegmentedButton
from .widgets._shared import _appearance_color, _master_background_color


class _FrameChildRegistry(dict):
    def __init__(self, owner: "Frame") -> None:
        super().__init__()
        self.owner = owner

    def __setitem__(self, key: str, widget: Any) -> None:
        super().__setitem__(key, widget)
        try:
            self.owner.canvas.children[key] = widget
        except Exception:
            pass
        self.owner._adopt_external_widget(widget)

    def __delitem__(self, key: str) -> None:
        widget = self.get(key)
        super().__delitem__(key)
        try:
            if self.owner.canvas.children.get(key) is widget:
                del self.owner.canvas.children[key]
        except Exception:
            pass


class Frame(Item):
    """Image-backed logical frame with frame-style child layout."""

    _BACKGROUND_KEYS = {
        "image",
        "fg_color",
        "opacity",
        "brightness",
        "border_radius",
        "corner_radius",
        "border_width",
        "border_color",
        "border_padding",
        "bg_opacity",
        "padx",
        "pady",
    }
    _FRAME_ONLY_KEYS = {
        "bg_color",
        "background_corner_colors",
        "overwrite_preferred_drawing_method",
    }

    @staticmethod
    def _usable_canvas(candidate: Any) -> bool:
        if candidate is None or not hasattr(candidate, "tk"):
            return False
        if not all(
            hasattr(candidate, method)
            for method in ("create_image", "create_window", "itemconfigure")
        ):
            return False
        try:
            return bool(candidate.winfo_exists())
        except (AttributeError, tk.TclError):
            return False

    @classmethod
    def _resolve_or_create_canvas(
        cls,
        master: Any,
        canvas: Any,
        width: int,
        height: int,
    ) -> tuple[Any, bool]:
        candidates = (
            canvas,
            getattr(master, "_content_canvas", None),
            getattr(master, "canvas", None),
            master if hasattr(master, "create_window") else None,
        )
        for candidate in candidates:
            if cls._usable_canvas(candidate):
                return candidate, False

        try:
            background = _appearance_color(
                _master_background_color(master),
                "#FFFFFF" if ctk.get_appearance_mode() == "Light" else "#000000",
            )
            created_canvas = ctk.CTkCanvas(
                master,
                width=max(1, int(width)),
                height=max(1, int(height)),
                bg=background,
                highlightthickness=0,
                bd=0,
            )
        except (AttributeError, TypeError, tk.TclError) as error:
            raise ValueError(
                "Frame could not find or create a canvas for its master."
            ) from error

        created_canvas._canvasctk_auto_created = True
        created_canvas._canvasctk_canvas_master = master
        return created_canvas, True

    def __init__(
        self,
        master: Any,
        width: int = 200,
        height: int = 200,
        corner_radius: int | None = None,
        border_width: int | None = None,
        bg_color: Any = "transparent",
        fg_color: Any = None,
        border_color: Any = None,
        background_corner_colors: Any = None,
        overwrite_preferred_drawing_method: str | None = None,
        *,
        canvas: Any = None,
        image: Any = None,
        opacity: float = 1,
        brightness: float = 1,
        border_radius: int | None = None,
        border_padding: Any = 2,
        bg_opacity: float = 1,
        padx: Any = 0,
        pady: Any = 0,
        x: int = 0,
        y: int = 0,
        anchor: str = "nw",
        **kwargs: Any,
    ) -> None:
        theme = ctk.ThemeManager.theme["CTkFrame"]
        theme_fg_option: str | bool = False
        uses_theme_border_color = border_color is None
        uses_theme_border_radius = corner_radius is None and border_radius is None
        uses_theme_border_width = border_width is None
        size = kwargs.pop("size", None)
        if size is not None:
            width, height = size
        if corner_radius is not None:
            border_radius = int(corner_radius)
            uses_theme_border_radius = False
        if fg_color is None:
            if isinstance(master, Frame) and master.cget("fg_color") == theme["fg_color"]:
                theme_fg_option = "top_fg_color"
            else:
                theme_fg_option = "fg_color"
            fg_color = theme[theme_fg_option]
        if border_color is None:
            border_color = theme["border_color"]
        if border_radius is None:
            border_radius = int(theme["corner_radius"])
        if border_width is None:
            border_width = int(theme["border_width"])

        shared_canvas, self._owns_canvas = self._resolve_or_create_canvas(
            master, canvas, width, height
        )
        self._owned_canvas_configure_id: str | None = None

        super().__init__(master, canvas=shared_canvas, **kwargs)
        if bg_color == "transparent":
            bg_color = _master_background_color(master, self.canvas)
        self._track_theme_defaults(
            "CTkFrame",
            fg_color=theme_fg_option,
            border_color=uses_theme_border_color,
            corner_radius=uses_theme_border_radius,
            border_width=uses_theme_border_width,
        )
        self.children = _FrameChildRegistry(self)
        self._x = int(x)
        self._y = int(y)
        # A Tk/CTk frame's configured width and height are desired fallback
        # dimensions. With geometry propagation enabled, managed grid/pack
        # children determine the requested size even when width/height were
        # explicitly supplied (including CTk's 200x200 defaults).
        self._auto_width = True
        self._auto_height = True
        self._pack_propagate = True
        self._grid_propagate = True
        # Tk freezes the current propagated request when propagation is
        # disabled.  Keep that request separate from the configured fallback
        # size so cget("width"/"height") remains unchanged.
        self._pack_frozen_size: tuple[int, int] | None = None
        self._grid_frozen_size: tuple[int, int] | None = None
        self._width = max(1, int(width if width is not None else 1))
        self._height = max(1, int(height if height is not None else 1))
        self._desired_width = self._width
        self._desired_height = self._height
        self._requested_width = self._width
        self._requested_height = self._height
        self._anchor = anchor
        self._child_widgets: IdentityRegistry[Any] = IdentityRegistry()
        self._child_manager_counts = {"grid": 0, "pack": 0, "place": 0}
        self._grid_bottom_counts: dict[int, int] = {}
        self._grid_bottom_heap: list[int] = []
        self._grid_bottom_by_child: dict[int, int] = {}
        self._child_windows: dict[Any, int] = {}
        self._child_layouts: dict[Any, tuple[str, dict[str, Any]]] = {}
        self._grid_column_options: dict[int, dict[str, Any]] = {}
        self._grid_row_options: dict[int, dict[str, Any]] = {}
        self._layout_pending = False
        self._layout_deferred = False
        self._layout_after_id: str | None = None
        self._is_laying_out = False
        self._destroying = False
        self._options: dict[str, Any] = {
            "width": self._width,
            "height": self._height,
            "bg_color": bg_color,
            "image": image,
            "fg_color": fg_color,
            "opacity": float(opacity),
            "brightness": float(brightness),
            "border_radius": int(border_radius),
            "corner_radius": int(border_radius),
            "border_width": int(border_width),
            "border_color": border_color,
            "background_corner_colors": background_corner_colors,
            "overwrite_preferred_drawing_method": overwrite_preferred_drawing_method,
            "border_padding": border_padding,
            "bg_opacity": float(bg_opacity),
            "padx": padx,
            "pady": pady,
            "x": self._x,
            "y": self._y,
            "anchor": self._anchor,
        }

        self._background = self.put(Image(
            self,
            canvas=self.canvas,
            image=image,
            width=self._width,
            height=self._height,
            anchor=self._anchor,
            x=self._x,
            y=self._y,
            fg_color=fg_color,
            opacity=opacity,
            brightness=brightness,
            border_radius=border_radius,
            border_width=border_width,
            border_color=border_color,
            border_padding=border_padding,
            bg_opacity=bg_opacity,
            padx=padx,
            pady=pady,
        ))
        self._corner_background_ids: list[int] = []
        self._corner_appearance_registered = False
        self._update_corner_appearance_tracking()
        self._sync_background_corners()
        self.hide()
        if self._owns_canvas:
            self._owned_canvas_configure_id = self.canvas.bind(
                "<Configure>", self._sync_owned_canvas_geometry, add="+"
            )

    def _owned_canvas_option(self, key: str, value: Any) -> Any:
        if key in {"in_", "before", "after"}:
            if isinstance(value, Frame) and getattr(value, "_owns_canvas", False):
                return value.canvas
            return value
        if key not in {"padx", "pady", "x", "y", "width", "height"}:
            return value

        scaling = max(float(self._widget_scaling), 1e-9)
        if isinstance(value, (tuple, list)):
            return tuple(int(round(float(part) * scaling)) for part in value)
        return int(round(float(value) * scaling))

    def _owned_canvas_geometry_options(
        self, manager: str, options: dict[str, Any]
    ) -> dict[str, Any]:
        native: dict[str, Any] = {}
        for key, value in options.items():
            if value is None:
                continue
            if manager == "pack" and key == "fill" and value in ("", "none"):
                continue
            native[key] = self._owned_canvas_option(key, value)
        return native

    def _set_owned_canvas_request(self) -> None:
        if not self._owns_canvas:
            return
        try:
            self.canvas.configure(
                width=max(1, int(round(self._apply_widget_scaling(self._requested_width)))),
                height=max(1, int(round(self._apply_widget_scaling(self._requested_height)))),
            )
        except tk.TclError:
            pass

    def _manage_owned_canvas(
        self, manager: str, options: dict[str, Any]
    ) -> None:
        self._grid_remove_options = None
        native_options = self._owned_canvas_geometry_options(manager, options)
        self._set_owned_canvas_request()
        if manager == "grid":
            self.canvas.grid(**native_options)
        elif manager == "pack":
            self.canvas.pack(**native_options)
        else:
            self.canvas.place(**native_options)
        self._layout_host = None
        self._layout_manager = manager
        self._layout_options = dict(options)
        self._show_from_geometry()
        try:
            self.canvas.after_idle(self._sync_owned_canvas_geometry)
        except tk.TclError:
            pass

    def _register_layout(self, manager: str, options: dict[str, Any]) -> None:
        if self._owns_canvas:
            return self._manage_owned_canvas(manager, options)
        return super()._register_layout(manager, options)

    def _register_place_layout(self, options: dict[str, Any]) -> None:
        if self._owns_canvas:
            return self._manage_owned_canvas("place", options)
        return super()._register_place_layout(options)

    def _sync_owned_canvas_geometry(self, event: Any = None) -> None:
        if not self._owns_canvas or self._destroying or self._destroyed:
            return
        if event is not None and getattr(event, "widget", self.canvas) is not self.canvas:
            return
        try:
            physical_width = int(
                getattr(event, "width", 0) or self.canvas.winfo_width()
            )
            physical_height = int(
                getattr(event, "height", 0) or self.canvas.winfo_height()
            )
        except tk.TclError:
            return
        width = max(1, int(round(self._reverse_widget_scaling(physical_width))))
        height = max(1, int(round(self._reverse_widget_scaling(physical_height))))
        self._x = 0
        self._y = 0
        self._anchor = "nw"
        changed = self._set_size(width, height)
        if changed:
            self._relayout_children()
        if self._layout_manager and self.canvas.winfo_ismapped():
            self.show()

    def _forget_layout(self, hide: bool = True, preserve_grid: bool = False) -> None:
        if not self._owns_canvas:
            return super()._forget_layout(hide=hide, preserve_grid=preserve_grid)
        manager = self._layout_manager
        try:
            if manager == "grid":
                if preserve_grid:
                    self.canvas.grid_remove()
                else:
                    self.canvas.grid_forget()
                    self._grid_remove_options = None
            elif manager == "pack":
                self.canvas.pack_forget()
            elif manager == "place":
                self.canvas.place_forget()
        except tk.TclError:
            pass
        self._layout_manager = ""
        self._layout_options = {}
        self._layout_host = None
        if hide:
            self.hide()

    def _detach_layout(self) -> None:
        if not self._owns_canvas:
            return super()._detach_layout()
        self._forget_layout(hide=False)
        self._release_canvas_item()

    def _update_corner_appearance_tracking(self) -> None:
        colors = self._options.get("background_corner_colors")
        needs_tracking = bool(
            colors
            and any(isinstance(color, (tuple, list)) for color in colors)
        )
        if needs_tracking and not self._corner_appearance_registered:
            AppearanceModeTracker.add(self._sync_background_corners, self.canvas)
            self._corner_appearance_registered = True
        elif not needs_tracking and self._corner_appearance_registered:
            AppearanceModeTracker.remove(self._sync_background_corners)
            self._corner_appearance_registered = False

    def _sync_background_corners(self, *_: Any) -> None:
        if not hasattr(self, "_corner_background_ids"):
            return
        colors = self._options.get("background_corner_colors")
        if colors is None:
            for item_id in self._corner_background_ids:
                self.canvas.itemconfigure(item_id, state="hidden")
            return
        if not isinstance(colors, (tuple, list)) or len(colors) != 4:
            raise ValueError("background_corner_colors must contain four colors or be None")
        while len(self._corner_background_ids) < 4:
            self._corner_background_ids.append(
                self.canvas.create_rectangle(0, 0, 1, 1, outline="", state="hidden")
            )
        left, top = self._origin()
        middle_x = left + self._width / 2
        middle_y = top + self._height / 2
        right = left + self._width
        bottom = top + self._height
        boxes = (
            (left, top, middle_x, middle_y),
            (middle_x, top, right, middle_y),
            (middle_x, middle_y, right, bottom),
            (left, middle_y, middle_x, bottom),
        )
        state = "normal" if self._is_rendered else "hidden"
        for item_id, color, box in zip(self._corner_background_ids, colors, boxes):
            x0, y0 = self._physical_point(box[0], box[1])
            x1, y1 = self._physical_point(box[2], box[3])
            self.canvas.coords(item_id, x0, y0, x1, y1)
            self.canvas.itemconfigure(item_id, fill=_appearance_color(color, str(self.canvas.cget("bg"))), state=state)
            self.canvas.tag_lower(item_id, self._background._image_id)

    def _widget_parent(self) -> Any:
        return self.canvas

    def _origin(self) -> tuple[int, int]:
        anchor = (self._anchor or "nw").lower()
        west_anchors = {"w", "nw", "sw"}
        east_anchors = {"e", "ne", "se"}
        north_anchors = {"n", "ne", "nw"}
        south_anchors = {"s", "se", "sw"}

        if anchor in east_anchors:
            left = self._x - self._width
        elif anchor in west_anchors:
            left = self._x
        else:
            left = self._x - self._width / 2

        if anchor in south_anchors:
            top = self._y - self._height
        elif anchor in north_anchors:
            top = self._y
        else:
            top = self._y - self._height / 2
        return int(round(left)), int(round(top))

    def _child_size(self, widget: Any) -> tuple[int, int]:
        if isinstance(widget, Item):
            # Tk computes geometry requests from the leaves upward.  Logical
            # CanvasCTk frames share one canvas and normally refresh through
            # idle callbacks, so a parent could otherwise measure a newly
            # gridded nested Frame at its stale 200x200 fallback size.  Refresh
            # the descendant's request before using it for this grid/pack row;
            # the descendant's queued layout still handles its actual drawing.
            if isinstance(widget, Frame) and widget is not self and not widget._is_laying_out:
                widget._refresh_auto_size()
            width = getattr(widget, "_requested_width", widget._width) if getattr(widget, "_auto_width", False) else widget._width
            height = getattr(widget, "_requested_height", widget._height) if getattr(widget, "_auto_height", False) else widget._height
            return max(1, int(width or 1)), max(1, int(height or 1))
        width_is_physical = True
        height_is_physical = True
        try:
            width = int(widget.winfo_reqwidth())
            height = int(widget.winfo_reqheight())
        except Exception:
            width, height = 1, 1
        if width <= 1:
            try:
                width = int(widget.cget("width"))
                width_is_physical = False
            except Exception:
                width = 1
        if height <= 1:
            try:
                height = int(widget.cget("height"))
                height_is_physical = False
            except Exception:
                height = 1
        return (
            max(1, int(round(self._reverse_widget_scaling(width) if width_is_physical else width))),
            max(1, int(round(self._reverse_widget_scaling(height) if height_is_physical else height))),
        )

    def _on_widget_scaling_changed(self, old_scaling: float, new_scaling: float) -> None:
        super()._on_widget_scaling_changed(old_scaling, new_scaling)
        if hasattr(self, "_background"):
            self._sync_background_corners()
            self.canvas.after_idle(self._relayout_children)

    def _set_size(self, width: int | None = None, height: int | None = None) -> bool:
        updates: dict[str, int] = {}
        if width is not None:
            width = max(1, int(width))
            if width != self._width:
                self._width = width
                updates["width"] = width
        if height is not None:
            height = max(1, int(height))
            if height != self._height:
                self._height = height
                updates["height"] = height
        if updates:
            self._background.configure(**updates)
            self._sync_background_corners()
            self._sync_packed_background_shape()
            return True
        return False

    def _packed_background_radius(self) -> int:
        # Tk's pack manager changes the allocation only; CTkFrame keeps its
        # configured corner radius even when it fills an axis. Flattening the
        # radius here made external pack padding look ineffective and produced
        # square-ended frames such as ScrollableTabview's strip.
        return int(self._options.get("border_radius", 0) or 0)

    def _sync_packed_background_shape(self) -> None:
        if not hasattr(self, "_background"):
            return
        radius = self._packed_background_radius()
        if self._background.border_radius != radius:
            self._background.configure(border_radius=radius)

    def _parent_controls_dimension(self, axis: str) -> bool:
        if self._layout_manager == "place":
            keys = ("width", "relwidth") if axis == "width" else ("height", "relheight")
            return any(key in self._layout_options for key in keys)
        if self._layout_manager == "grid":
            # Grid owns the current allocation on both axes, even without
            # sticky.  Normally that allocation equals the natural request;
            # when the grid cell is smaller it is deliberately constrained to
            # the cell.  Treating only an e/w or n/s-sticky dimension as
            # parent-controlled let auto-size immediately restore the larger
            # request, moving the frame back outside the window.
            return True
        if self._layout_manager == "pack":
            fill = str(self._layout_options.get("fill", "") or "").lower()
            dimension_fill = "x" if axis == "width" else "y"
            return fill in (dimension_fill, "both")
        return False

    def _canvas_size(self) -> tuple[int, int]:
        width = int(round(self._reverse_widget_scaling(self.canvas.winfo_width())))
        height = int(round(self._reverse_widget_scaling(self.canvas.winfo_height())))
        if width <= 1:
            width = int(round(self._reverse_widget_scaling(float(self.canvas.cget("width")))))
        if height <= 1:
            height = int(round(self._reverse_widget_scaling(float(self.canvas.cget("height")))))
        return width, height

    def _reapply_outer_place(self) -> None:
        if self._layout_manager == "place":
            width, height = self._canvas_size()
            self._apply_place_layout(width, height)

    @staticmethod
    def _grid_indices(index: Any) -> tuple[int, ...]:
        if isinstance(index, (tuple, list, set)):
            return tuple(int(value) for value in index)
        return (int(index),)

    def _grid_track_configure(
        self,
        store: dict[int, dict[str, Any]],
        index: Any,
        cnf: Any = None,
        **kwargs: Any,
    ) -> Any:
        options = dict(cnf) if isinstance(cnf, dict) else {}
        options.update(kwargs)
        is_query = (isinstance(cnf, str) and not kwargs) or not options
        if index == "all":
            if is_query:
                raise tk.TclError('expected integer but got "all"')
            columns, rows = self.grid_size()
            count = columns if store is self._grid_column_options else rows
            indices = tuple(range(count))
        else:
            try:
                indices = self._grid_indices(index)
            except (TypeError, ValueError) as error:
                raise tk.TclError(f'expected integer but got "{index}"') from error

        defaults = {"minsize": 0, "pad": 0, "uniform": None, "weight": 0}
        if isinstance(cnf, str) and not kwargs:
            if len(indices) != 1:
                raise tk.TclError("query requires a single grid index")
            return {**defaults, **store.get(indices[0], {})}.get(cnf, "")

        if not options:
            if len(indices) != 1:
                raise tk.TclError("query requires a single grid index")
            return {**defaults, **store.get(indices[0], {})}

        unknown = next((key for key in options if key not in defaults), None)
        if unknown is not None:
            raise tk.TclError(f"bad option '-{unknown}': must be -minsize, -pad, -uniform, or -weight")
        normalized = dict(options)
        for key in ("minsize", "pad", "weight"):
            if key in normalized:
                normalized[key] = int(normalized[key])
                if normalized[key] < 0:
                    raise tk.TclError(f"-{key} must be non-negative")
        if "uniform" in normalized and normalized["uniform"] in ("", None):
            normalized["uniform"] = None

        for track in indices:
            configured = store.setdefault(track, {})
            configured.update(normalized)
        self._relayout_children()
        return None

    def grid_columnconfigure(self, index: Any, cnf: Any = None, **kwargs: Any) -> Any:
        return self._grid_track_configure(self._grid_column_options, index, cnf, **kwargs)

    grid_columnconfig = grid_columnconfigure
    columnconfigure = grid_columnconfigure

    def grid_rowconfigure(self, index: Any, cnf: Any = None, **kwargs: Any) -> Any:
        return self._grid_track_configure(self._grid_row_options, index, cnf, **kwargs)

    grid_rowconfig = grid_rowconfigure
    rowconfigure = grid_rowconfigure

    def grid_anchor(self, anchor: str | None = None) -> str | None:
        if anchor is None:
            # tkinter's grid_anchor wrapper discards Tcl's query result.
            return None
        value = str(anchor).lower()
        if value not in {"n", "ne", "e", "se", "s", "sw", "w", "nw", "center"}:
            raise tk.TclError(
                f'bad anchor "{value}": must be n, ne, e, se, s, sw, w, nw, or center'
            )
        if value != self._grid_anchor_value:
            self._grid_anchor_value = value
            self._schedule_child_layout()
        return None

    def grid_size(self) -> tuple[int, int]:
        children = [widget for widget in self._child_layouts if self._child_layouts[widget][0] == "grid"]
        columns = max(
            [
                int(self._child_layouts[widget][1].get("column", 0))
                + int(self._child_layouts[widget][1].get("columnspan", 1))
                for widget in children
            ]
            + [index + 1 for index in self._grid_column_options]
            + [0]
        )
        rows = max(
            [
                int(self._child_layouts[widget][1].get("row", 0))
                + int(self._child_layouts[widget][1].get("rowspan", 1))
                for widget in children
            ]
            + [index + 1 for index in self._grid_row_options]
            + [0]
        )
        return columns, rows

    def _grid_track_sizes(self) -> tuple[list[int], list[int]]:
        columns, rows = self.grid_size()
        column_widths = [0] * columns
        row_heights = [0] * rows
        for widget, (manager, options) in self._child_layouts.items():
            if manager != "grid":
                continue
            column = int(options.get("column", 0))
            row = int(options.get("row", 0))
            columnspan = max(1, int(options.get("columnspan", 1)))
            rowspan = max(1, int(options.get("rowspan", 1)))
            padx0, padx1 = self._pad(options.get("padx", 0))
            pady0, pady1 = self._pad(options.get("pady", 0))
            ipadx = max(0, int(options.get("ipadx", 0) or 0))
            ipady = max(0, int(options.get("ipady", 0) or 0))
            req_width, req_height = self._child_size(widget)
            width_share = max(1, (req_width + ipadx * 2 + padx0 + padx1 + columnspan - 1) // columnspan)
            height_share = max(1, (req_height + ipady * 2 + pady0 + pady1 + rowspan - 1) // rowspan)
            for track in range(column, min(column + columnspan, columns)):
                column_widths[track] = max(column_widths[track], width_share)
            for track in range(row, min(row + rowspan, rows)):
                row_heights[track] = max(row_heights[track], height_share)
        self._apply_grid_track_options(column_widths, self._grid_column_options, self._width)
        self._apply_grid_track_options(row_heights, self._grid_row_options, self._height)
        return column_widths, row_heights

    def grid_bbox(
        self,
        column: int | None = None,
        row: int | None = None,
        col2: int | None = None,
        row2: int | None = None,
    ) -> tuple[int, int, int, int]:
        solution = self._grid_solution(allocated=True)
        widths = [max(0.0, float(value)) for value in solution.column_sizes]
        heights = [max(0.0, float(value)) for value in solution.row_sizes]
        if not widths or not heights:
            return 0, 0, 0, 0
        first_column = 0 if column is None else max(0, min(len(widths) - 1, int(column)))
        first_row = 0 if row is None else max(0, min(len(heights) - 1, int(row)))
        last_column = len(widths) - 1 if col2 is None else max(first_column, min(len(widths) - 1, int(col2)))
        last_row = len(heights) - 1 if row2 is None else max(first_row, min(len(heights) - 1, int(row2)))
        frame_left, frame_top = self._origin()
        x = solution.origin_x - frame_left + sum(widths[:first_column])
        y = solution.origin_y - frame_top + sum(heights[:first_row])
        width = sum(widths[first_column:last_column + 1])
        height = sum(heights[first_row:last_row + 1])
        return tuple(
            tk_round_distance(self._apply_widget_scaling(value))
            for value in (x, y, width, height)
        )

    def grid_location(self, x: int, y: int) -> tuple[int, int]:
        solution = self._grid_solution(allocated=True)
        widths = [max(0.0, float(value)) for value in solution.column_sizes]
        heights = [max(0.0, float(value)) for value in solution.row_sizes]
        frame_left, frame_top = self._origin()
        logical_x = self._reverse_widget_scaling(x) - (solution.origin_x - frame_left)
        logical_y = self._reverse_widget_scaling(y) - (solution.origin_y - frame_top)

        def locate(value: float, tracks: list[float]) -> int:
            if value < 0:
                return -1
            offset = 0
            for index, size in enumerate(tracks):
                offset += size
                if value < offset:
                    return index
            return len(tracks)

        return locate(logical_x, widths), locate(logical_y, heights)

    @staticmethod
    def _apply_grid_track_options(
        sizes: list[int],
        configured: dict[int, dict[str, Any]],
        available: int | None = None,
    ) -> None:
        for index, options in configured.items():
            if index >= len(sizes):
                continue
            minimum = max(0, int(options.get("minsize", 0) or 0))
            padding = max(0, int(options.get("pad", 0) or 0))
            sizes[index] = max(sizes[index], minimum + padding)

        uniform_groups: dict[str, list[tuple[int, int]]] = {}
        for index in range(len(sizes)):
            uniform = configured.get(index, {}).get("uniform")
            if uniform not in (None, ""):
                weight = max(1, int(configured.get(index, {}).get("weight", 0) or 0))
                uniform_groups.setdefault(str(uniform), []).append((index, weight))
        for tracks in uniform_groups.values():
            unit = max((sizes[index] + weight - 1) // weight for index, weight in tracks)
            for index, weight in tracks:
                sizes[index] = unit * weight

        if available is None:
            return
        Item._distribute_grid_space(sizes, configured, int(available))

    def _grid_request_size(self) -> tuple[int, int]:
        children = [widget for widget in self._child_layouts if self._child_layouts[widget][0] == "grid"]
        if not children and not self._grid_column_options and not self._grid_row_options:
            return 0, 0

        columns = max(
            [int(self._child_layouts[widget][1].get("column", 0)) + int(self._child_layouts[widget][1].get("columnspan", 1)) for widget in children]
            + [index + 1 for index in self._grid_column_options]
            + [1]
        )
        rows = max(
            [int(self._child_layouts[widget][1].get("row", 0)) + int(self._child_layouts[widget][1].get("rowspan", 1)) for widget in children]
            + [index + 1 for index in self._grid_row_options]
            + [1]
        )
        column_widths = [0] * max(1, columns)
        row_heights = [0] * max(1, rows)

        for widget in children:
            options = self._child_layouts[widget][1]
            column = int(options.get("column", 0))
            row = int(options.get("row", 0))
            columnspan = max(1, int(options.get("columnspan", 1)))
            rowspan = max(1, int(options.get("rowspan", 1)))
            padx0, padx1 = self._pad(options.get("padx", 0))
            pady0, pady1 = self._pad(options.get("pady", 0))
            ipadx = max(0, int(options.get("ipadx", 0) or 0))
            ipady = max(0, int(options.get("ipady", 0) or 0))
            req_width, req_height = self._child_size(widget)
            width_share = max(1, int((req_width + ipadx * 2 + padx0 + padx1 + columnspan - 1) / columnspan))
            height_share = max(1, int((req_height + ipady * 2 + pady0 + pady1 + rowspan - 1) / rowspan))
            for index in range(column, min(column + columnspan, len(column_widths))):
                column_widths[index] = max(column_widths[index], width_share)
            for index in range(row, min(row + rowspan, len(row_heights))):
                row_heights[index] = max(row_heights[index], height_share)

        self._apply_grid_track_options(column_widths, self._grid_column_options)
        self._apply_grid_track_options(row_heights, self._grid_row_options)
        return sum(column_widths), sum(row_heights)

    def _pack_request_size(self) -> tuple[int, int]:
        children = [widget for widget in self._child_layouts if self._child_layouts[widget][0] == "pack"]
        if not children:
            return 0, 0

        width = 0
        height = 0
        for widget in children:
            options = self._child_layouts[widget][1]
            padx0, padx1 = self._pad(options.get("padx", 0))
            pady0, pady1 = self._pad(options.get("pady", 0))
            ipadx = max(0, int(options.get("ipadx", 0) or 0))
            ipady = max(0, int(options.get("ipady", 0) or 0))
            side = str(options.get("side", "top") or "top").lower()
            req_width, req_height = self._child_size(widget)
            outer_width = req_width + ipadx * 2 + padx0 + padx1
            outer_height = req_height + ipady * 2 + pady0 + pady1
            if side in ("left", "right"):
                width += outer_width
                height = max(height, outer_height)
            else:
                width = max(width, outer_width)
                height += outer_height
        return width, height

    def _refresh_auto_size(self) -> None:
        requests: list[tuple[int, int]] = []
        has_grid_children = any(manager == "grid" for manager, _ in self._child_layouts.values())
        has_pack_children = any(manager == "pack" for manager, _ in self._child_layouts.values())
        if self._grid_propagate and (has_grid_children or self._grid_column_options or self._grid_row_options):
            requests.append(self._grid_request_size())
        if self._pack_propagate and has_pack_children:
            requests.append(self._pack_request_size())
        if requests:
            width = max(1, *(request_width for request_width, _ in requests))
            height = max(1, *(request_height for _, request_height in requests))
        elif has_grid_children and not self._grid_propagate and self._grid_frozen_size is not None:
            width, height = self._grid_frozen_size
        elif has_pack_children and not self._pack_propagate and self._pack_frozen_size is not None:
            width, height = self._pack_frozen_size
        else:
            width = self._desired_width
            height = self._desired_height
        requested_changed = False
        if width != self._requested_width:
            self._requested_width = width
            requested_changed = True
        if height != self._requested_height:
            self._requested_height = height
            requested_changed = True

        # Geometry managers own the current allocation on every axis, even
        # when the allocation only differs from the natural request because
        # of ipad, a grid cell, or a pack parcel.  Propagation changes the
        # request reported to the parent; it must never overwrite an active
        # manager allocation.
        changed = self._set_size(
            width if not self._parent_controls_dimension("width") else None,
            height if not self._parent_controls_dimension("height") else None,
        )
        if changed:
            self._reapply_outer_place()
        if requested_changed:
            if self._owns_canvas:
                self._set_owned_canvas_request()
            elif self._canvas_host is not None and not self._canvas_host._is_laying_out:
                self._canvas_host._schedule_child_layout()
            elif self._canvas_host is None and self._layout_manager:
                # Direct children of Window's shared canvas still need their
                # outer grid/pack allocation recomputed when propagation
                # changes the request reported to that geometry manager.
                self._schedule_canvas_layout()

    def _set_child_position(
        self,
        widget: Any,
        left: float,
        top: float,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        if self._destroying or self._destroyed or getattr(widget, "_destroyed", False):
            return
        if isinstance(widget, Item):
            widget._resize_for_place(width, height)
            target_origin = int(round(left)), int(round(top))
            if widget._winfo_origin() != target_origin:
                widget._move_bbox(left, top)
            if not self._is_rendered:
                was_hidden = widget.is_hidden
                widget.hide()
                widget.is_hidden = was_hidden
            elif widget.is_hidden:
                widget.hide()
            elif not widget._is_rendered:
                widget.show()
            return

        window_id = self._child_windows.get(widget)
        if window_id is None:
            return
        config: dict[str, Any] = {
            "anchor": "nw",
            "state": "hidden" if not self._is_rendered or getattr(widget, "is_hidden", False) else "normal",
            "width": max(1, int(width)) if width is not None else 0,
            "height": max(1, int(height)) if height is not None else 0,
        }
        physical_left, physical_top = self._physical_point(left, top)
        if width is not None:
            config["width"] = max(1, int(round(self._apply_widget_scaling(width))))
        if height is not None:
            config["height"] = max(1, int(round(self._apply_widget_scaling(height))))
        self.canvas.coords(window_id, physical_left, physical_top)
        self.canvas.itemconfigure(window_id, **config)
        self.canvas.tag_raise(window_id)

    def _validate_child_manager(self, widget: Any, manager: str) -> None:
        if manager not in {"grid", "pack"}:
            return
        conflicting = "pack" if manager == "grid" else "grid"
        current_manager = self._child_layouts.get(widget, ("", {}))[0]
        conflicting_count = self._child_manager_counts.get(conflicting, 0)
        if current_manager == conflicting:
            conflicting_count -= 1
        if conflicting_count > 0:
            raise tk.TclError(
                f"cannot use geometry manager {manager} inside {self.winfo_name()} "
                f"which already has slaves managed by {conflicting}"
            )

    def _next_implicit_grid_row(self, widget: Any = None) -> int:
        """Match Tk's implicit row selection for ``child.grid()``."""
        ignored_bottom = self._grid_bottom_by_child.get(id(widget))
        if ignored_bottom is None or self._grid_bottom_counts.get(ignored_bottom, 0) > 1:
            while self._grid_bottom_heap and not self._grid_bottom_counts.get(-self._grid_bottom_heap[0], 0):
                heappop(self._grid_bottom_heap)
            return -self._grid_bottom_heap[0] if self._grid_bottom_heap else 0
        return max(
            (bottom for bottom, count in self._grid_bottom_counts.items() if count and bottom != ignored_bottom),
            default=0,
        )

    def _attach_child_item(self, widget: Item, manager: str, options: dict[str, Any]) -> None:
        self._validate_child_manager(widget, manager)
        if widget not in self._child_widgets:
            self._child_widgets.append(widget)
        if id(widget) not in self._element_identity_keys:
            self.put(widget)
        self._record_child_layout(widget, manager, options)
        self._schedule_child_layout()

    def _record_child_layout(self, widget: Any, manager: str, options: dict[str, Any]) -> None:
        clean_options = dict(options)
        before = clean_options.pop("before", None)
        after = clean_options.pop("after", None)
        if before is not None and after is not None:
            raise tk.TclError("can't specify both -after and -before")

        reference = before if before is not None else after
        if reference is not None:
            if manager != "pack":
                raise tk.TclError("-before and -after are only valid for pack")
            if reference is widget or self._child_layouts.get(reference, ("", {}))[0] != "pack":
                raise tk.TclError("window specified for -before/-after is not packed")
            entries = [(child, layout) for child, layout in self._child_layouts.items() if child is not widget]
            index = next(i for i, (child, _) in enumerate(entries) if child is reference)
            entries.insert(index if before is not None else index + 1, (widget, (manager, clean_options)))
            self._unaccount_child_layout(widget, self._child_layouts.get(widget))
            self._child_layouts = dict(entries)
        else:
            self._unaccount_child_layout(widget, self._child_layouts.get(widget))
            self._child_layouts[widget] = (manager, clean_options)
        self._account_child_layout(widget, manager, clean_options)

        if isinstance(widget, Item):
            widget._layout_options = dict(clean_options)
        elif hasattr(widget, "_canvas_ui_layout_options"):
            widget._canvas_ui_layout_options = dict(clean_options)

    def _account_child_layout(self, widget: Any, manager: str, options: dict[str, Any]) -> None:
        self._child_manager_counts[manager] = self._child_manager_counts.get(manager, 0) + 1
        if manager == "grid":
            bottom = int(options.get("row", 0)) + max(1, int(options.get("rowspan", 1)))
            self._grid_bottom_by_child[id(widget)] = bottom
            self._grid_bottom_counts[bottom] = self._grid_bottom_counts.get(bottom, 0) + 1
            heappush(self._grid_bottom_heap, -bottom)

    def _unaccount_child_layout(self, widget: Any, layout: Any) -> None:
        if layout is None:
            return
        manager, _options = layout
        self._child_manager_counts[manager] = max(0, self._child_manager_counts.get(manager, 0) - 1)
        if manager == "grid":
            bottom = self._grid_bottom_by_child.pop(id(widget), None)
            if bottom is not None:
                remaining = self._grid_bottom_counts.get(bottom, 0) - 1
                if remaining > 0:
                    self._grid_bottom_counts[bottom] = remaining
                else:
                    self._grid_bottom_counts.pop(bottom, None)

    @staticmethod
    def _merge_geometry_options(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if args:
            value = args[0]
            if isinstance(value, dict):
                options.update(value)
        options.update(kwargs)
        return options

    def _adopt_external_widget(self, widget: Any) -> None:
        if isinstance(widget, Element) or getattr(widget, "_canvas_ui_host", None) is self:
            return

        old_host = getattr(widget, "_canvas_ui_host", None)
        if old_host is not None and old_host is not self:
            try:
                old_host._detach_child_widget(widget)
            except Exception:
                pass

        originals = getattr(widget, "_canvas_ui_original_geometry", None)
        if originals is None:
            originals = {
                "grid": getattr(widget, "grid", None),
                "pack": getattr(widget, "pack", None),
                "place": getattr(widget, "place", None),
                "grid_forget": getattr(widget, "grid_forget", None),
                "grid_remove": getattr(widget, "grid_remove", None),
                "pack_forget": getattr(widget, "pack_forget", None),
                "place_forget": getattr(widget, "place_forget", None),
                "grid_info": getattr(widget, "grid_info", None),
                "pack_info": getattr(widget, "pack_info", None),
                "place_info": getattr(widget, "place_info", None),
                "winfo_manager": getattr(widget, "winfo_manager", None),
                "destroy": getattr(widget, "destroy", None),
            }
            widget._canvas_ui_original_geometry = originals

        widget._canvas_ui_host = self
        widget._canvas_ui_layout_host = self
        widget._canvas_ui_layout_manager = ""
        widget._canvas_ui_layout_options = {}
        widget._canvas_ui_grid_remove_options = None

        def resolve_host(target: Any = None) -> "Frame":
            if target is None or target is self:
                return self
            if (
                getattr(target, "canvas", None) is self.canvas
                and hasattr(target, "_attach_child_widget")
            ):
                return target
            if (
                getattr(target, "_content_canvas", None) is self.canvas
                and hasattr(target, "_attach_child_widget")
            ):
                return target
            raise tk.TclError(f'cannot use geometry manager inside {target!s}')

        def normalized(
            manager: str,
            supplied: dict[str, Any],
            layout_host: "Frame",
        ) -> dict[str, Any]:
            supplied = dict(supplied)
            if "in" in supplied and "in_" not in supplied:
                supplied["in_"] = supplied.pop("in")
            if manager == "grid":
                allowed = {"row", "column", "rowspan", "columnspan", "padx", "pady", "ipadx", "ipady", "sticky", "in_"}
                unknown = next((key for key in supplied if key not in allowed), None)
                if unknown is not None:
                    raise tk.TclError(f"bad option '-{unknown}'")
                restoring_grid = (
                    widget._canvas_ui_layout_manager == "grid"
                    or widget._canvas_ui_grid_remove_options is not None
                )
                options = {
                    "row": 0,
                    "column": 0,
                    "rowspan": 1,
                    "columnspan": 1,
                    "padx": 0,
                    "pady": 0,
                    "ipadx": 0,
                    "ipady": 0,
                    "sticky": "",
                }
                if widget._canvas_ui_layout_manager == "grid":
                    options.update(widget._canvas_ui_layout_options)
                elif widget._canvas_ui_grid_remove_options is not None:
                    options.update(widget._canvas_ui_grid_remove_options)
                if "row" not in supplied and not restoring_grid:
                    options["row"] = layout_host._next_implicit_grid_row(widget)
                options.update(supplied)
                options["row"] = int(options["row"])
                options["column"] = int(options["column"])
                options["rowspan"] = int(options["rowspan"])
                options["columnspan"] = int(options["columnspan"])
                sticky_value = str(options.get("sticky", "") or "").lower()
                options["sticky"] = "".join(
                    character for character in "nesw" if character in sticky_value
                )
                if options["row"] < 0 or options["column"] < 0:
                    raise tk.TclError("row and column must be non-negative")
                if options["rowspan"] < 1 or options["columnspan"] < 1:
                    raise tk.TclError("rowspan and columnspan must be positive")
                if any(character not in "nsew" for character in options["sticky"]):
                    raise tk.TclError(
                        f'bad stickyness value "{options["sticky"]}": must be a string containing n, e, s, and/or w'
                    )
                widget._canvas_ui_grid_remove_options = None
                return options
            if manager == "pack":
                allowed = {
                    "side", "padx", "pady", "ipadx", "ipady", "anchor", "fill", "expand",
                    "before", "after", "in_",
                }
                unknown = next((key for key in supplied if key not in allowed), None)
                if unknown is not None:
                    raise tk.TclError(f"bad option '-{unknown}'")
                options = {
                    "side": "top",
                    "padx": 0,
                    "pady": 0,
                    "ipadx": 0,
                    "ipady": 0,
                    "anchor": "center",
                    "fill": "",
                    "expand": False,
                }
                if widget._canvas_ui_layout_manager == "pack":
                    options.update(widget._canvas_ui_layout_options)
                options.update(supplied)
                if options.get("before") is not None and options.get("after") is not None:
                    raise tk.TclError("can't specify both -after and -before")
                options["side"] = str(options["side"] or "top").lower()
                options["anchor"] = str(options["anchor"] or "center").lower()
                options["fill"] = str(options["fill"] or "").lower()
                if options["side"] not in {"top", "bottom", "left", "right"}:
                    raise tk.TclError(f'bad side "{options["side"]}": must be top, bottom, left, or right')
                if options["fill"] not in {"", "none", "x", "y", "both"}:
                    raise tk.TclError(f'bad fill style "{options["fill"]}": must be none, x, y, or both')
                if options["anchor"] not in {"n", "ne", "e", "se", "s", "sw", "w", "nw", "center"}:
                    raise tk.TclError(
                        f'bad anchor "{options["anchor"]}": must be n, ne, e, se, s, sw, w, nw, or center'
                    )
                options["fill"] = "" if options["fill"] == "none" else options["fill"]
                options["expand"] = bool(self.tk.getboolean(options["expand"]))
                widget._canvas_ui_grid_remove_options = None
                return options
            allowed = {"x", "y", "relx", "rely", "width", "height", "relwidth", "relheight", "anchor", "bordermode", "in_"}
            unknown = next((key for key in supplied if key not in allowed), None)
            if unknown is not None:
                raise tk.TclError(f"bad option '-{unknown}'")
            options = {
                "x": 0,
                "y": 0,
                "relx": 0,
                "rely": 0,
                "anchor": "nw",
                "bordermode": "inside",
            }
            if widget._canvas_ui_layout_manager == "place":
                options.update(widget._canvas_ui_layout_options)
            for key, value in supplied.items():
                if key in {"width", "height", "relwidth", "relheight"} and value == "":
                    options.pop(key, None)
                else:
                    options[key] = value
            options["anchor"] = str(options.get("anchor", "nw") or "nw").lower()
            options["bordermode"] = str(options.get("bordermode", "inside") or "inside").lower()
            if options["anchor"] not in {"n", "ne", "e", "se", "s", "sw", "w", "nw", "center"}:
                raise tk.TclError(
                    f'bad anchor "{options["anchor"]}": must be n, ne, e, se, s, sw, w, nw, or center'
                )
            if options["bordermode"] not in {"inside", "outside", "ignore"}:
                raise tk.TclError(
                    f'bad bordermode "{options["bordermode"]}": must be inside, outside, or ignore'
                )
            widget._canvas_ui_grid_remove_options = None
            return options

        def layout(manager: str, *args: Any, **kwargs: Any) -> Any:
            supplied = self._merge_geometry_options(args, kwargs)
            if manager == "place" and not supplied and widget._canvas_ui_layout_manager != "place":
                return None
            target = supplied.get("in_", supplied.get("in"))
            if target is None and widget._canvas_ui_layout_manager == manager:
                target = widget._canvas_ui_layout_options.get("in_")
            layout_host = resolve_host(target)
            options = normalized(manager, supplied, layout_host)
            previous_host = getattr(widget, "_canvas_ui_layout_host", self)
            layout_host._validate_child_manager(widget, manager)
            if previous_host is not layout_host:
                previous_host._detach_child_widget(widget)
            widget._canvas_ui_layout_host = layout_host
            widget._canvas_ui_layout_manager = manager
            widget._canvas_ui_layout_options = dict(options)
            layout_host._attach_child_widget(widget, manager, options)
            return None

        def public_place(*args: Any, **kwargs: Any) -> Any:
            supplied = self._merge_geometry_options(args, kwargs)
            if "width" in supplied or "height" in supplied:
                raise ValueError(
                    "'width' and 'height' arguments must be passed to the constructor "
                    "of the widget, not the place method"
                )
            return layout("place", **supplied)

        def forget(manager: str, preserve_grid: bool = False, *_: Any, **__: Any) -> None:
            if widget._canvas_ui_layout_manager != manager:
                return
            if preserve_grid:
                widget._canvas_ui_grid_remove_options = dict(widget._canvas_ui_layout_options)
            elif manager == "grid":
                widget._canvas_ui_grid_remove_options = None
            widget._canvas_ui_layout_manager = ""
            widget._canvas_ui_layout_options = {}
            widget._canvas_ui_layout_host._forget_child_widget(widget)

        def info(manager: str, *_: Any, **__: Any) -> dict[str, Any]:
            if widget._canvas_ui_layout_manager == manager:
                uses_ctk_arguments = callable(getattr(widget, "_apply_argument_scaling", None))
                options = normalize_solver_options(
                    widget._canvas_ui_layout_options,
                    manager,
                    self._widget_scaling,
                    ctk_arguments=uses_ctk_arguments,
                )
                scaling = max(float(self._widget_scaling), 1e-9)

                def physical(value: Any) -> Any:
                    if isinstance(value, tuple):
                        return tuple(tk_round_distance(float(part) * scaling) for part in value)
                    if isinstance(value, (int, float)):
                        return tk_round_distance(float(value) * scaling)
                    return value

                if manager in {"grid", "pack"}:
                    for key in ("padx", "pady", "ipadx", "ipady"):
                        if key in options:
                            options[key] = physical(options[key])
                if manager == "pack":
                    options["expand"] = int(bool(options.get("expand", False)))
                    options["fill"] = str(options.get("fill", "") or "none")
                options["in"] = options.pop("in_", None) or widget._canvas_ui_layout_host
                if manager == "place":
                    options.setdefault("width", "")
                    options.setdefault("height", "")
                    options.setdefault("relwidth", "")
                    options.setdefault("relheight", "")
                    for key in ("x", "y", "width", "height", "relx", "rely", "relwidth", "relheight"):
                        value = options.get(key, "")
                        if value != "":
                            if key in {"x", "y"} and isinstance(value, (int, float)):
                                value = tk_round_distance(float(value) * scaling)
                            options[key] = str(value)
                return options
            if manager == "pack":
                raise tk.TclError(f'window "{widget}" isn\'t packed')
            return {}

        def configure_layout(manager: str, *args: Any, **kwargs: Any) -> Any:
            if widget._canvas_ui_layout_manager == manager:
                options = dict(widget._canvas_ui_layout_options)
            elif manager == "grid":
                options = dict(widget._canvas_ui_grid_remove_options or {})
            else:
                options = {}
            options.update(self._merge_geometry_options(args, kwargs))
            return layout(manager, **options)

        def destroy(*args: Any, **kwargs: Any) -> Any:
            getattr(widget, "_canvas_ui_layout_host", self)._detach_child_widget(widget)
            original_destroy = originals.get("destroy")
            if original_destroy is not None:
                return original_destroy(*args, **kwargs)
            return None

        widget.grid = lambda *args, **kwargs: layout("grid", *args, **kwargs)
        widget.pack = lambda *args, **kwargs: layout("pack", *args, **kwargs)
        widget.place = lambda *args, **kwargs: layout("place", *args, **kwargs)
        widget.grid_configure = lambda *args, **kwargs: configure_layout("grid", *args, **kwargs)
        widget.grid_config = widget.grid_configure
        widget.pack_configure = lambda *args, **kwargs: configure_layout("pack", *args, **kwargs)
        widget.pack_config = widget.pack_configure
        widget.place_configure = lambda *args, **kwargs: configure_layout("place", *args, **kwargs)
        widget.place_config = widget.place_configure
        widget.grid_forget = lambda *args, **kwargs: forget("grid", False, *args, **kwargs)
        widget.grid_remove = lambda *args, **kwargs: forget("grid", True, *args, **kwargs)
        widget.pack_forget = lambda *args, **kwargs: forget("pack", False, *args, **kwargs)
        widget.place_forget = lambda *args, **kwargs: forget("place", False, *args, **kwargs)
        widget.grid_info = lambda *args, **kwargs: info("grid", *args, **kwargs)
        widget.pack_info = lambda *args, **kwargs: info("pack", *args, **kwargs)
        widget.place_info = lambda *args, **kwargs: info("place", *args, **kwargs)
        widget.winfo_manager = lambda: widget._canvas_ui_layout_manager
        widget.destroy = destroy

    def _attach_child_widget(self, widget: Any, manager: str, options: dict[str, Any]) -> None:
        self._validate_child_manager(widget, manager)
        if widget not in self._child_widgets:
            self._child_widgets.append(widget)
        if isinstance(widget, Element) and id(widget) not in self._element_identity_keys:
            self.put(widget)
        if widget not in self._child_windows:
            window_id = self.canvas.create_window(0, 0, window=widget, anchor="nw", state="hidden")
            self._child_windows[widget] = window_id
            try:
                widget.bind("<Configure>", lambda _event, child=widget: self._schedule_child_layout(child), add="+")
            except Exception:
                pass
        self._record_child_layout(widget, manager, options)
        self._schedule_child_layout()

    def _detach_child_widget(self, widget: Any) -> None:
        if self._destroying:
            # The complete subtree and its canvas items are already being
            # destroyed. Updating every intermediate registry turns teardown
            # into quadratic work and schedules layouts that can never render.
            return
        window_id = self._child_windows.pop(widget, None)
        if window_id is not None:
            try:
                self.canvas.delete(window_id)
            except Exception:
                pass
        layout = self._child_layouts.pop(widget, None)
        self._unaccount_child_layout(widget, layout)
        if widget in self._child_widgets:
            self._child_widgets.remove(widget)
        key = self._element_identity_keys.pop(id(widget), None)
        if key is not None and self.elements.get(key) is widget:
            self.elements.pop(key, None)
        self._schedule_child_layout()

    def _forget_child_widget(self, widget: Any, hide: bool = True) -> None:
        if self._destroying:
            return
        layout = self._child_layouts.pop(widget, None)
        self._unaccount_child_layout(widget, layout)
        if hide:
            self._hide_child_widget(widget)
        self._schedule_child_layout()

    def _hide_child_widget(self, widget: Any) -> None:
        if isinstance(widget, Item):
            widget.hide()
            return
        window_id = self._child_windows.get(widget)
        if window_id is not None:
            self.canvas.itemconfigure(window_id, state="hidden")

    def _show_child_widget(self, widget: Any) -> None:
        if self._destroying or self._destroyed or getattr(widget, "_destroyed", False):
            return
        # A logical child remains in ``elements`` after grid/pack/place_forget
        # so it can be managed again later. Item.show() walks owned elements
        # when a parent becomes visible, which can temporarily resurrect one
        # of these unmanaged children at its stale coordinates. Keep geometry
        # manager visibility authoritative across parent/tab hide-show cycles.
        if widget not in self._child_layouts:
            self._hide_child_widget(widget)
            return
        if not self._is_rendered:
            return
        if isinstance(widget, Item):
            if widget.is_hidden:
                widget._is_rendered = False
                widget._hide()
            elif not widget._is_rendered:
                widget.show()
            return
        window_id = self._child_windows.get(widget)
        if window_id is not None:
            self.canvas.itemconfigure(window_id, state="normal")

    def _schedule_child_layout(self, _: Any = None) -> None:
        if self._destroying or self._destroyed:
            return
        if not self._is_rendered or not self._host_is_rendered():
            self._layout_deferred = True
            return
        if self._layout_pending:
            return
        self._layout_pending = True
        self._layout_after_id = self.canvas.after_idle(self._flush_child_layout)

    def _flush_child_layout(self) -> None:
        self._layout_after_id = None
        if self._destroying or self._destroyed:
            self._layout_pending = False
            self._layout_deferred = False
            return
        if not self._is_rendered or not self._host_is_rendered():
            self._layout_pending = False
            self._layout_deferred = True
            return
        self._layout_pending = False
        self._layout_deferred = False
        self._relayout_children()

    def _relayout_children(self) -> None:
        if self._is_laying_out or self._destroying or self._destroyed:
            return
        self._is_laying_out = True
        try:
            self._refresh_auto_size()
            self._layout_grid_children()
            self._layout_pack_children()
            self._layout_place_children()
        finally:
            self._is_laying_out = False

    def _layout_grid_children(self) -> None:
        children = [
            widget for widget in self._child_layouts
            if self._child_layouts[widget][0] == "grid"
            and not getattr(widget, "_destroyed", False)
        ]
        if not children:
            return

        columns = max(
            [int(self._child_layouts[widget][1].get("column", 0)) + int(self._child_layouts[widget][1].get("columnspan", 1)) for widget in children]
            + [index + 1 for index in self._grid_column_options]
        )
        rows = max(
            [int(self._child_layouts[widget][1].get("row", 0)) + int(self._child_layouts[widget][1].get("rowspan", 1)) for widget in children]
            + [index + 1 for index in self._grid_row_options]
        )
        column_widths = [0] * max(1, columns)
        row_heights = [0] * max(1, rows)

        for widget in children:
            options = self._child_layouts[widget][1]
            column = int(options.get("column", 0))
            row = int(options.get("row", 0))
            columnspan = max(1, int(options.get("columnspan", 1)))
            rowspan = max(1, int(options.get("rowspan", 1)))
            padx0, padx1 = self._pad(options.get("padx", 0))
            pady0, pady1 = self._pad(options.get("pady", 0))
            ipadx = max(0, int(options.get("ipadx", 0) or 0))
            ipady = max(0, int(options.get("ipady", 0) or 0))
            req_width, req_height = self._child_size(widget)
            width_share = max(1, int((req_width + ipadx * 2 + padx0 + padx1 + columnspan - 1) / columnspan))
            height_share = max(1, int((req_height + ipady * 2 + pady0 + pady1 + rowspan - 1) / rowspan))
            for index in range(column, min(column + columnspan, len(column_widths))):
                column_widths[index] = max(column_widths[index], width_share)
            for index in range(row, min(row + rowspan, len(row_heights))):
                row_heights[index] = max(row_heights[index], height_share)

        self._apply_grid_track_options(column_widths, self._grid_column_options, self._width)
        self._apply_grid_track_options(row_heights, self._grid_row_options, self._height)

        origin_x, origin_y = self._origin()
        column_offsets = [0]
        for value in column_widths[:-1]:
            column_offsets.append(column_offsets[-1] + value)
        row_offsets = [0]
        for value in row_heights[:-1]:
            row_offsets.append(row_offsets[-1] + value)

        for widget in children:
            options = self._child_layouts[widget][1]
            column = int(options.get("column", 0))
            row = int(options.get("row", 0))
            columnspan = max(1, int(options.get("columnspan", 1)))
            rowspan = max(1, int(options.get("rowspan", 1)))
            padx0, padx1 = self._pad(options.get("padx", 0))
            pady0, pady1 = self._pad(options.get("pady", 0))
            ipadx = max(0, int(options.get("ipadx", 0) or 0))
            ipady = max(0, int(options.get("ipady", 0) or 0))
            sticky = str(options.get("sticky", "") or "").lower()
            req_width, req_height = self._child_size(widget)
            natural_width = req_width + ipadx * 2
            natural_height = req_height + ipady * 2

            cell_left = origin_x + column_offsets[column]
            cell_top = origin_y + row_offsets[row]
            cell_width = sum(column_widths[column:column + columnspan])
            cell_height = sum(row_heights[row:row + rowspan])
            inner_left = cell_left + padx0
            inner_top = cell_top + pady0
            inner_width = max(1, cell_width - padx0 - padx1)
            inner_height = max(1, cell_height - pady0 - pady1)
            # Grid tracks may shrink below a child's natural request.  Canvas
            # items are not clipped by a native Tk parent, so allowing the
            # natural size here would center part of the child outside its
            # frame/window.  Constrain only the overflowing dimension; a child
            # that fits keeps its normal requested size and anchor semantics.
            child_width = (
                inner_width
                if "e" in sticky and "w" in sticky
                else min(natural_width, inner_width)
            )
            child_height = (
                inner_height
                if "n" in sticky and "s" in sticky
                else min(natural_height, inner_height)
            )
            left = inner_left if "w" in sticky else inner_left + inner_width - child_width if "e" in sticky else inner_left + (inner_width - child_width) / 2
            top = inner_top if "n" in sticky else inner_top + inner_height - child_height if "s" in sticky else inner_top + (inner_height - child_height) / 2
            self._set_child_position(widget, left, top, child_width if child_width != req_width else None, child_height if child_height != req_height else None)

    def _layout_pack_children(self) -> None:
        children = [
            widget for widget in self._child_layouts
            if self._child_layouts[widget][0] == "pack"
            and not getattr(widget, "_destroyed", False)
        ]
        if not children:
            return

        origin_x, origin_y = self._origin()
        left_edge, top_edge = float(origin_x), float(origin_y)
        right_edge, bottom_edge = float(origin_x + self._width), float(origin_y + self._height)

        vertical_expanders = sum(
            1
            for widget in children
            if self._child_layouts[widget][1].get("expand")
            and str(self._child_layouts[widget][1].get("side", "top")).lower() in {"top", "bottom"}
        )
        horizontal_expanders = sum(
            1
            for widget in children
            if self._child_layouts[widget][1].get("expand")
            and str(self._child_layouts[widget][1].get("side", "top")).lower() in {"left", "right"}
        )
        vertical_request = 0
        horizontal_request = 0
        for widget in children:
            options = self._child_layouts[widget][1]
            padx0, padx1 = self._pad(options.get("padx", 0))
            pady0, pady1 = self._pad(options.get("pady", 0))
            ipadx = max(0, int(options.get("ipadx", 0) or 0))
            ipady = max(0, int(options.get("ipady", 0) or 0))
            req_width, req_height = self._child_size(widget)
            if str(options.get("side", "top") or "top").lower() in {"top", "bottom"}:
                vertical_request += req_height + ipady * 2 + pady0 + pady1
            else:
                horizontal_request += req_width + ipadx * 2 + padx0 + padx1
        vertical_extra = max(0, self._height - vertical_request)
        horizontal_extra = max(0, self._width - horizontal_request)
        vertical_index = horizontal_index = 0

        for widget in children:
            options = self._child_layouts[widget][1]
            padx0, padx1 = self._pad(options.get("padx", 0))
            pady0, pady1 = self._pad(options.get("pady", 0))
            side = str(options.get("side", "top") or "top").lower()
            anchor = str(options.get("anchor", "center") or "center").lower()
            fill = str(options.get("fill", "") or "").lower()
            expand = bool(options.get("expand", False))
            fill_x = fill in ("x", "both")
            fill_y = fill in ("y", "both")
            north_anchors = {"n", "ne", "nw"}
            south_anchors = {"s", "se", "sw"}
            west_anchors = {"w", "nw", "sw"}
            east_anchors = {"e", "ne", "se"}
            req_width, req_height = self._child_size(widget)
            ipadx = max(0, int(options.get("ipadx", 0) or 0))
            ipady = max(0, int(options.get("ipady", 0) or 0))
            natural_width = req_width + ipadx * 2
            natural_height = req_height + ipady * 2

            if side in ("left", "right"):
                extra = 0
                if expand and horizontal_expanders:
                    quotient, remainder = divmod(horizontal_extra, horizontal_expanders)
                    extra = quotient + (1 if horizontal_index < remainder else 0)
                    horizontal_index += 1
                remaining_width = max(1.0, right_edge - left_edge)
                parcel_width = min(natural_width + padx0 + padx1 + extra, remaining_width)
                parcel_left = left_edge if side == "left" else right_edge - parcel_width
                parcel_top = top_edge
                parcel_height = max(1.0, bottom_edge - top_edge)
                available_width = max(1, int(parcel_width - padx0 - padx1))
                available_height = max(1, int(parcel_height - pady0 - pady1))
                child_width = available_width if fill_x else natural_width
                child_height = available_height if fill_y else natural_height
                inner_left = parcel_left + padx0
                inner_top = parcel_top + pady0
                if fill_x or anchor in west_anchors:
                    left = inner_left
                elif anchor in east_anchors:
                    left = inner_left + available_width - child_width
                else:
                    left = inner_left + (available_width - child_width) / 2
                if fill_y or anchor in north_anchors:
                    top = inner_top
                elif anchor in south_anchors:
                    top = inner_top + available_height - child_height
                else:
                    top = inner_top + (available_height - child_height) / 2
                if side == "left":
                    left_edge += parcel_width
                else:
                    right_edge -= parcel_width
            else:
                extra = 0
                if expand and vertical_expanders:
                    quotient, remainder = divmod(vertical_extra, vertical_expanders)
                    extra = quotient + (1 if vertical_index < remainder else 0)
                    vertical_index += 1
                remaining_height = max(1.0, bottom_edge - top_edge)
                parcel_height = min(natural_height + pady0 + pady1 + extra, remaining_height)
                parcel_left = left_edge
                parcel_top = top_edge if side == "top" else bottom_edge - parcel_height
                parcel_width = max(1.0, right_edge - left_edge)
                available_width = max(1, int(parcel_width - padx0 - padx1))
                available_height = max(1, int(parcel_height - pady0 - pady1))
                child_width = available_width if fill_x else natural_width
                child_height = available_height if fill_y else natural_height
                inner_left = parcel_left + padx0
                inner_top = parcel_top + pady0
                if fill_x or anchor in west_anchors:
                    left = inner_left
                elif anchor in east_anchors:
                    left = inner_left + available_width - child_width
                else:
                    left = inner_left + (available_width - child_width) / 2
                if fill_y or anchor in north_anchors:
                    top = inner_top
                elif anchor in south_anchors:
                    top = inner_top + available_height - child_height
                else:
                    top = inner_top + (available_height - child_height) / 2
                if side == "top":
                    top_edge += parcel_height
                else:
                    bottom_edge -= parcel_height

            self._set_child_position(widget, left, top, child_width if child_width != req_width else None, child_height if child_height != req_height else None)

    def _layout_place_children(self) -> None:
        origin_x, origin_y = self._origin()
        for widget in [
            child for child in self._child_layouts
            if self._child_layouts[child][0] == "place"
            and not getattr(child, "_destroyed", False)
        ]:
            options = self._child_layouts[widget][1]
            req_width, req_height = self._child_size(widget)
            child_width = req_width
            child_height = req_height
            if "width" in options or "relwidth" in options:
                child_width = max(1, int(round(float(options.get("width", 0) or 0) + float(options.get("relwidth", 0) or 0) * self._width)))
            if "height" in options or "relheight" in options:
                child_height = max(1, int(round(float(options.get("height", 0) or 0) + float(options.get("relheight", 0) or 0) * self._height)))

            x = origin_x + int(round(float(options.get("x", 0) or 0) + float(options.get("relx", 0) or 0) * self._width))
            y = origin_y + int(round(float(options.get("y", 0) or 0) + float(options.get("rely", 0) or 0) * self._height))
            anchor = str(options.get("anchor", "nw") or "nw").lower()
            west_anchors = {"w", "nw", "sw"}
            east_anchors = {"e", "ne", "se"}
            north_anchors = {"n", "ne", "nw"}
            south_anchors = {"s", "se", "sw"}

            if anchor in east_anchors:
                left = x - child_width
            elif anchor in west_anchors:
                left = x
            else:
                left = x - child_width / 2

            if anchor in south_anchors:
                top = y - child_height
            elif anchor in north_anchors:
                top = y
            else:
                top = y - child_height / 2
            self._set_child_position(widget, left, top, child_width if child_width != req_width else None, child_height if child_height != req_height else None)

    # Shared geometry path -------------------------------------------------
    # These definitions intentionally replace the older per-manager
    # approximations above.  Top-level Items use the same pure solvers, so a
    # geometry option has one meaning regardless of which CanvasCTk container
    # owns the child.
    def _geometry_overhaul_children_disabled(self, manager: str) -> list[GeometryChild]:
        result: list[GeometryChild] = []
        for widget, (active_manager, options) in self._child_layouts.items():
            if active_manager != manager:
                continue
            width, height = self._child_size(widget)
            scaling = max(float(self._widget_scaling), 1e-9)
            width = tk_round_distance(float(width) * scaling) / scaling
            height = tk_round_distance(float(height) * scaling) / scaling
            uses_ctk_arguments = isinstance(widget, Item) or callable(
                getattr(widget, "_apply_argument_scaling", None)
            )
            solver_options = normalize_solver_options(
                options,
                manager,
                scaling,
                ctk_arguments=uses_ctk_arguments,
            )
            if manager == "place":
                for key in getattr(widget, "_place_physical_keys", ()):
                    value = options.get(key)
                    if isinstance(value, (int, float)):
                        solver_options[key] = logical_pixel_distance(value, scaling)
            result.append(GeometryChild(widget, width, height, solver_options))
        return result

    def _logical_grid_track_options(
        self,
        options: dict[int, dict[str, Any]],
    ) -> dict[int, dict[str, Any]]:
        """Convert native Tk track distances to the solver's logical units."""
        scaling = max(float(self._widget_scaling), 1e-9)
        result: dict[int, dict[str, Any]] = {}
        for index, values in options.items():
            normalized = dict(values)
            for key in ("minsize", "pad"):
                if key in normalized and normalized[key] not in (None, ""):
                    normalized[key] = logical_pixel_distance(normalized[key], scaling)
            result[index] = normalized
        return result

    def _grid_solution(self, *, allocated: bool) -> Any:
        origin_x, origin_y = self._origin()
        return solve_grid(
            self._geometry_children("grid"),
            self._width if allocated else None,
            self._height if allocated else None,
            column_options=self._logical_grid_track_options(self._grid_column_options),
            row_options=self._logical_grid_track_options(self._grid_row_options),
            anchor=self._grid_anchor_value,
            origin_x=origin_x if allocated else 0,
            origin_y=origin_y if allocated else 0,
        )

    def _pack_solution(self, *, allocated: bool) -> Any:
        origin_x, origin_y = self._origin()
        return solve_pack(
            self._geometry_children("pack"),
            self._width if allocated else None,
            self._height if allocated else None,
            origin_x=origin_x if allocated else 0,
            origin_y=origin_y if allocated else 0,
        )

    def _geometry_overhaul_grid_request_size_disabled(self) -> tuple[int, int]:
        solution = self._grid_solution(allocated=False)
        return max(1, int(round(solution.request_width))), max(1, int(round(solution.request_height)))

    def _geometry_overhaul_pack_request_size_disabled(self) -> tuple[int, int]:
        solution = self._pack_solution(allocated=False)
        return max(1, int(round(solution.request_width))), max(1, int(round(solution.request_height)))

    def _geometry_overhaul_grid_track_sizes_disabled(self) -> tuple[list[int], list[int]]:
        solution = self._grid_solution(allocated=True)
        return (
            [max(0, int(round(value))) for value in solution.column_sizes],
            [max(0, int(round(value))) for value in solution.row_sizes],
        )

    def _geometry_overhaul_layout_grid_children_disabled(self) -> None:
        for allocation in self._grid_solution(allocated=True).allocations:
            self._set_child_position(
                allocation.key,
                allocation.x,
                allocation.y,
                max(1, int(round(allocation.width))),
                max(1, int(round(allocation.height))),
            )

    def _geometry_overhaul_layout_pack_children_disabled(self) -> None:
        for allocation in self._pack_solution(allocated=True).allocations:
            self._set_child_position(
                allocation.key,
                allocation.x,
                allocation.y,
                max(1, int(round(allocation.width))),
                max(1, int(round(allocation.height))),
            )

    def _geometry_overhaul_layout_place_children_disabled(self) -> None:
        origin_x, origin_y = self._origin()
        for child in self._geometry_children("place"):
            allocation = solve_place(
                child,
                self._width,
                self._height,
                origin_x=origin_x,
                origin_y=origin_y,
                # CTkFrame's border is canvas artwork, not Tk's native
                # geometry border.  Tk place therefore sees a zero-width
                # master border for CTk/CanvasCTk frames.
                border_width=0,
            )
            self._set_child_position(
                allocation.key,
                allocation.x,
                allocation.y,
                max(1, int(round(allocation.width))),
                max(1, int(round(allocation.height))),
            )

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        if not hasattr(self, "_background"):
            return
        old_surface = _master_background_color(self, self.canvas) if "fg_color" in kwargs else None
        background_updates: dict[str, Any] = {}
        relayout = False
        corners_changed = False
        for key, value in kwargs.items():
            if key == "width":
                value = max(1, int(value))
                if value != self._desired_width:
                    self._desired_width = value
                    self._options["width"] = value
                    if self._grid_frozen_size is not None:
                        self._grid_frozen_size = (value, self._grid_frozen_size[1])
                    if self._pack_frozen_size is not None:
                        self._pack_frozen_size = (value, self._pack_frozen_size[1])
                    relayout = True
            elif key == "height":
                value = max(1, int(value))
                if value != self._desired_height:
                    self._desired_height = value
                    self._options["height"] = value
                    if self._grid_frozen_size is not None:
                        self._grid_frozen_size = (self._grid_frozen_size[0], value)
                    if self._pack_frozen_size is not None:
                        self._pack_frozen_size = (self._pack_frozen_size[0], value)
                    relayout = True
            elif key == "size":
                width, height = value
                width, height = max(1, int(width)), max(1, int(height))
                if width != self._desired_width or height != self._desired_height:
                    self._desired_width, self._desired_height = width, height
                    self._options["width"], self._options["height"] = width, height
                    if self._grid_frozen_size is not None:
                        self._grid_frozen_size = (width, height)
                    if self._pack_frozen_size is not None:
                        self._pack_frozen_size = (width, height)
                    relayout = True
            elif key == "x":
                value = int(value)
                if value != self._x:
                    self._x = value
                    self._options["x"] = value
                    background_updates["x"] = value
                    relayout = True
                    corners_changed = True
            elif key == "y":
                value = int(value)
                if value != self._y:
                    self._y = value
                    self._options["y"] = value
                    background_updates["y"] = value
                    relayout = True
                    corners_changed = True
            elif key == "anchor":
                value = str(value)
                if value != self._anchor:
                    self._set_anchor(value)
                    self._options["anchor"] = self._anchor
                    relayout = True
                    corners_changed = True
            elif key in self._BACKGROUND_KEYS:
                mapped_key = "border_radius" if key == "corner_radius" else key
                if key in ("border_radius", "corner_radius"):
                    value = int(value)
                if self._options.get(mapped_key) != value or require_redraw:
                    self._options[mapped_key] = value
                    if key in ("border_radius", "corner_radius"):
                        self._options["corner_radius"] = value
                        self._options["border_radius"] = value
                    background_updates[mapped_key] = value
                    corners_changed = True
            elif key in self._FRAME_ONLY_KEYS:
                if key == "bg_color" and value == "transparent":
                    value = _master_background_color(self.master, self.canvas)
                if self._options.get(key) != value or require_redraw:
                    self._options[key] = value
                    if key in {"bg_color", "background_corner_colors"}:
                        corners_changed = True
        if background_updates:
            self._background.configure(**background_updates)
        if "background_corner_colors" in kwargs:
            self._update_corner_appearance_tracking()
        if corners_changed:
            self._sync_background_corners()
        if old_surface is not None and "fg_color" in background_updates:
            new_surface = _master_background_color(self, self.canvas)
            for child in self.winfo_children():
                try:
                    if child.cget("bg_color") == old_surface:
                        child.configure(bg_color=new_surface)
                except (AttributeError, KeyError, TypeError, ValueError, tk.TclError):
                    pass
        if background_updates or relayout:
            self._sync_packed_background_shape()
        if relayout:
            self._relayout_children()
            if self._canvas_host is not None:
                if not self._canvas_host._is_laying_out:
                    self._canvas_host._relayout_children()
            elif self._layout_manager:
                self._schedule_canvas_layout()

    config = configure

    def cget(self, key: str) -> Any:
        if key in {"bg", "background"}:
            return _master_background_color(self, self.canvas)
        if key == "corner_radius":
            return self._options.get("border_radius")
        return self._options.get(key)

    def winfo_children(self) -> list[Any]:
        children = list(self._child_widgets)
        # Native Tk/CTk children are registered as soon as they are created,
        # before a geometry manager is selected. Tk's winfo_children() includes
        # those unmanaged widgets too.
        for widget in self.children.values():
            if widget not in children:
                children.append(widget)
        return children

    def winfo_reqwidth(self) -> int:
        return max(1, int(round(self._apply_widget_scaling(self._requested_width))))

    def winfo_reqheight(self) -> int:
        return max(1, int(round(self._apply_widget_scaling(self._requested_height))))

    def grid_slaves(self, row: int | None = None, column: int | None = None) -> list[Any]:
        # Tk returns gridded slaves in stacking/most-recently-managed order.
        children = [
            widget
            for widget in reversed(self._child_layouts)
            if self._child_layouts[widget][0] == "grid"
        ]
        if row is not None:
            children = [widget for widget in children if int(self._child_layouts[widget][1].get("row", 0)) == int(row)]
        if column is not None:
            children = [widget for widget in children if int(self._child_layouts[widget][1].get("column", 0)) == int(column)]
        return children

    def pack_slaves(self) -> list[Any]:
        return [widget for widget in self._child_layouts if self._child_layouts[widget][0] == "pack"]

    def _propagate_value(self, flag: Any) -> bool:
        return bool(self.tk.getboolean(flag))

    def pack_propagate(self, flag: Any = tk.Misc._noarg_) -> bool | None:
        """Set or query whether packed children determine this Frame's automatic size."""
        if flag is tk.Misc._noarg_:
            return self._pack_propagate
        enabled = self._propagate_value(flag)
        if enabled != self._pack_propagate:
            if not enabled:
                if not self._is_laying_out:
                    self._refresh_auto_size()
                self._pack_frozen_size = (
                    self._requested_width,
                    self._requested_height,
                )
            else:
                self._pack_frozen_size = None
            self._pack_propagate = enabled
            self._schedule_child_layout()
        return None

    propagate = pack_propagate

    def grid_propagate(self, flag: Any = tk.Misc._noarg_) -> bool | None:
        """Set or query whether gridded children determine this Frame's automatic size."""
        if flag is tk.Misc._noarg_:
            return self._grid_propagate
        enabled = self._propagate_value(flag)
        if enabled != self._grid_propagate:
            if not enabled:
                if not self._is_laying_out:
                    self._refresh_auto_size()
                self._grid_frozen_size = (
                    self._requested_width,
                    self._requested_height,
                )
            else:
                self._grid_frozen_size = None
            self._grid_propagate = enabled
            self._schedule_child_layout()
        return None

    def place_slaves(self) -> list[Any]:
        return [widget for widget in self._child_layouts if self._child_layouts[widget][0] == "place"]

    def _set_anchor(self, anchor: str) -> None:
        self._anchor = anchor
        self._background.configure(anchor=anchor)

    def _resize_for_place(self, width: int | None, height: int | None) -> None:
        target_width = self._requested_width if width is None else width
        target_height = self._requested_height if height is None else height
        if self._set_size(width=target_width, height=target_height):
            self._relayout_children()

    def place(
        self,
        x: int | None = None,
        y: int | None = None,
        relx: float | None = None,
        rely: float | None = None,
        width: Any = None,
        height: Any = None,
        relwidth: Any = None,
        relheight: Any = None,
        anchor: str | None = None,
        **kwargs: Any,
    ) -> None:
        return super().place(
            x=x,
            y=y,
            relx=relx,
            rely=rely,
            width=width,
            height=height,
            relwidth=relwidth,
            relheight=relheight,
            anchor=anchor,
            **kwargs,
        )

    def move(self, x: int, y: int) -> None:
        self._x, self._y = int(x), int(y)
        self._options["x"] = self._x
        self._options["y"] = self._y
        self._background.move(self._x, self._y)
        self._sync_background_corners()
        self._relayout_children()

    def bind(
        self,
        sequence: str | None = None,
        command: Any = None,
        add: str | bool | None = True,
    ) -> None:
        if add not in ("+", True):
            raise ValueError("'add' argument can only be '+' or True to preserve internal callbacks")
        if self._is_lifecycle_event(sequence):
            self._bind_lifecycle_event(sequence, command, add)
            return None
        if sequence is not None and command is not None:
            self.canvas.tag_bind(self._background._image_id, sequence, command, add="+")
        # CTkFrame intentionally discards the underlying Canvas.bind return
        # value, including for bind queries.
        return None

    def unbind(self, sequence: str | None = None, funcid: str | None = None) -> None:
        if funcid is not None:
            raise ValueError(
                "'funcid' argument can only be None, because removing one Tcl callback "
                "can also remove internal widget callbacks"
            )
        if self._is_lifecycle_event(sequence):
            self._unbind_lifecycle_event(sequence)
            return
        if sequence is not None:
            self.canvas.tag_unbind(self._background._image_id, sequence)

    def hide(self, hide: bool = True) -> None:
        if not hide:
            self.show()
            return
        self._show_requested = False
        self.is_hidden = True
        self._is_rendered = False
        self._hide()

    def show(self, show: bool = True) -> None:
        if not show or not self.enabled:
            self.hide()
            return
        self._show_requested = True
        self.is_hidden = False
        if not self._host_is_rendered():
            self._is_rendered = False
            self._hide()
            return
        self._is_rendered = True
        self._show()

    def _hide(self) -> None:
        self._background.hide()
        for item_id in self._corner_background_ids:
            self.canvas.itemconfigure(item_id, state="hidden")
        for widget in self._child_widgets:
            previous = getattr(widget, "is_hidden", None)
            self._hide_child_widget(widget)
            if previous is not None:
                widget.is_hidden = previous

    def _show(self) -> None:
        if self._layout_pending or self._layout_deferred:
            if self._layout_after_id is not None:
                try:
                    self.canvas.after_cancel(self._layout_after_id)
                except tk.TclError:
                    pass
                self._layout_after_id = None
            self._layout_pending = False
            self._layout_deferred = False
            self._relayout_children()
        self._sync_packed_background_shape()
        self._background.show()
        self._sync_background_corners()
        for widget in self._child_widgets:
            self._show_child_widget(widget)

    def destroy(self) -> None:
        if self._destroying or self._destroyed:
            return
        self._destroying = True
        if self._layout_after_id is not None:
            try:
                self.canvas.after_cancel(self._layout_after_id)
            except tk.TclError:
                pass
            self._layout_after_id = None
        self._layout_pending = False
        self._layout_deferred = False
        if self._corner_appearance_registered:
            AppearanceModeTracker.remove(self._sync_background_corners)
            self._corner_appearance_registered = False
        self._detach_layout()
        self._cleanup_canvas_element()
        for item_id in self._corner_background_ids:
            self.canvas.delete(item_id)
        self._corner_background_ids.clear()
        for window_id in list(self._child_windows.values()):
            try:
                self.canvas.delete(window_id)
            except Exception:
                pass
        self._child_windows.clear()
        self._child_widgets.clear()
        self._child_layouts.clear()
        if self._owns_canvas:
            try:
                self.canvas.destroy()
            except tk.TclError:
                pass


class TabView(Frame):
    """Canvas port of the structure and selection model of ``CTkTabview``."""

    _outer_spacing = 10
    _outer_button_overhang = 8
    _button_height = 26
    _segmented_button_border_width = 3

    def __init__(
        self,
        master: Any,
        width: int = 300,
        height: int = 250,
        corner_radius: int | None = None,
        border_width: int | None = None,
        bg_color: Any = "transparent",
        fg_color: Any = None,
        border_color: Any = None,
        segmented_button_fg_color: Any = None,
        segmented_button_selected_color: Any = None,
        segmented_button_selected_hover_color: Any = None,
        segmented_button_unselected_color: Any = None,
        segmented_button_unselected_hover_color: Any = None,
        text_color: Any = None,
        text_color_disabled: Any = None,
        command: Any = None,
        anchor: str = "center",
        state: str = "normal",
        **kwargs: Any,
    ) -> None:
        self._tab_anchor = str(anchor)
        self._tab_state = str(state)
        self._command = command
        super().__init__(
            master,
            width=width,
            height=height,
            bg_color=bg_color,
            fg_color=fg_color,
            bg_opacity=1,
            corner_radius=corner_radius,
            border_width=border_width,
            border_color=border_color,
            **kwargs,
        )
        self._tab_corner_radius = int(self.cget("corner_radius"))
        self._tab_border_width = int(self.cget("border_width"))
        self._tab_fg_color = self.cget("fg_color")
        self._tab_border_color = self.cget("border_color")
        self._tab_dict: dict[str, Frame] = {}
        self._name_list: list[str] = []
        self._current_name = ""
        self._segmented_button = SegmentedButton(
            self,
            height=self._button_height,
            border_width=self._segmented_button_border_width,
            fg_color=segmented_button_fg_color,
            selected_color=segmented_button_selected_color,
            selected_hover_color=segmented_button_selected_hover_color,
            unselected_color=segmented_button_unselected_color,
            unselected_hover_color=segmented_button_unselected_hover_color,
            text_color=text_color,
            text_color_disabled=text_color_disabled,
            values=[],
            command=self._segmented_button_callback,
            state=self._tab_state,
        )
        # Keep tab content on the same canvas as the TabView. A nested Tk canvas
        # is always an opaque child window, so it blocks CanvasCTk opacity and
        # transparent fg_color behavior for the tab frame.
        self._content = Frame(
            self,
            canvas=self.canvas,
            width=1,
            height=1,
            corner_radius=0,
            border_width=0,
            fg_color="transparent",
        )
        self._content.place(x=0, y=0, width=1, height=1, anchor="nw")
        self._layout_internal_parts()

    def _layout_internal_parts(self) -> None:
        top_anchor = self._tab_anchor.lower() not in {"s", "sw", "se"}
        content_offset = self._outer_spacing + self._button_height - self._outer_button_overhang
        if top_anchor:
            self._segmented_button.place(relx=0.5, x=0, y=0, anchor="n")
            content_y = content_offset
        else:
            self._segmented_button.place(relx=0.5, x=0, rely=1, y=0, anchor="s")
            content_y = 0
        content_width = max(1, self._width)
        content_height = max(1, self._height - content_offset)
        self._content.place(x=0, y=content_y, width=content_width, height=content_height, anchor="nw")
        self.canvas.tag_raise(self._segmented_button._canvas._root_tag)

    def _refresh_auto_size(self) -> None:
        """Include the selected tab's propagated request in the outer widget."""
        width = self._desired_width
        height = self._desired_height
        if hasattr(self, "_content"):
            if not self._content._is_laying_out:
                self._content._refresh_auto_size()
            content_offset = self._outer_spacing + self._button_height - self._outer_button_overhang
            width = max(width, self._content._requested_width)
            height = max(height, self._content._requested_height + content_offset)
        if hasattr(self, "_segmented_button"):
            width = max(width, self._segmented_button._width)

        requested_changed = width != self._requested_width or height != self._requested_height
        self._requested_width = width
        self._requested_height = height
        changed = self._set_size(
            width if not self._layout_manager else None,
            height if not self._layout_manager else None,
        )
        if changed:
            self._reapply_outer_place()
        if requested_changed:
            if self._canvas_host is not None and not self._canvas_host._is_laying_out:
                self._canvas_host._schedule_child_layout()
            elif self._canvas_host is None and self._layout_manager:
                self._schedule_canvas_layout()

    def _segmented_button_callback(self, selected_name: str) -> None:
        self.set(selected_name)
        if self._command is not None:
            self._command()

    def _switch_tab_visibility(self, old_name: str, new_name: str) -> None:
        """Switch content by touching only the two participating frames."""
        if old_name == new_name:
            return

        old_frame = self._tab_dict.get(old_name)
        if old_frame is not None:
            if old_frame.winfo_manager() == "pack":
                # Geometry removal already hides the complete logical subtree.
                old_frame.pack_forget()
            elif old_frame._is_rendered:
                old_frame.hide()

        selected_frame = self._tab_dict.get(new_name)
        if selected_frame is None:
            return
        if selected_frame.winfo_manager() != "pack":
            selected_frame.pack(fill="both", expand=True)
            # Place and reveal selected content synchronously. This prevents a
            # newly-created shared-canvas frame flashing at canvas origin.
            self._content._relayout_children()
        elif not selected_frame._is_rendered:
            selected_frame.show()

    def _sync_tab_visibility(self) -> None:
        """Recover visibility after the complete TabView was hidden/shown."""
        selected_frame = self._tab_dict.get(self._current_name)
        for frame in self._tab_dict.values():
            if frame is selected_frame:
                continue
            if frame.winfo_manager() == "pack":
                frame.pack_forget()
            elif frame._is_rendered:
                frame.hide()
        if selected_frame is not None:
            if selected_frame.winfo_manager() != "pack":
                selected_frame.pack(fill="both", expand=True)
                self._content._relayout_children()
            elif not selected_frame._is_rendered:
                selected_frame.show()

    def add(self, name: str) -> Frame:
        return self.insert(len(self._name_list), name)

    def add_many(self, names: Any) -> list[Frame]:
        """Add a validated batch of tabs and redraw the strip exactly once."""
        batch = list(names)
        if any(not isinstance(name, str) for name in batch):
            raise ValueError("Tab names must be strings")
        if len(set(batch)) != len(batch):
            raise ValueError("Tab names in a batch must be unique")
        duplicate = next((name for name in batch if name in self._tab_dict), None)
        if duplicate is not None:
            raise ValueError(f"Tab already exists: {duplicate}")
        if not batch:
            return []

        was_empty = not self._tab_dict
        frames: list[Frame] = []
        for name in batch:
            frame = Frame(self._content, fg_color="transparent")
            # Unmanaged logical frames otherwise briefly exist at (0, 0).
            frame.hide()
            self._tab_dict[name] = frame
            self._name_list.append(name)
            frames.append(frame)

        self._segmented_button.configure(values=self._name_list)
        if was_empty:
            first = batch[0]
            old_name = self._current_name
            self._current_name = first
            self._segmented_button.set(first)
            self._switch_tab_visibility(old_name, first)
        elif self._current_name:
            self._segmented_button.set(self._current_name)
        return frames

    def insert(self, index: int, name: str) -> Frame:
        if name in self._tab_dict:
            raise ValueError(f"Tab already exists: {name}")
        if not 0 <= index <= len(self._name_list):
            raise ValueError(f"Tab index {index} not in range")
        is_first_tab = not self._tab_dict
        frame = Frame(self._content, fg_color="transparent")
        # Keep new inactive content hidden from its first canvas frame.
        frame.hide()
        self._tab_dict[name] = frame
        self._name_list.insert(index, name)
        self._segmented_button.configure(values=self._name_list)
        if is_first_tab:
            old_name = self._current_name
            self._current_name = name
            self._segmented_button.set(name)
            self._switch_tab_visibility(old_name, name)
        elif self._current_name:
            self._segmented_button.set(self._current_name)
        return frame

    def tab(self, name: str) -> Frame:
        if name not in self._tab_dict:
            raise ValueError(f"Unknown tab: {name}")
        return self._tab_dict[name]

    def index(self, name: str) -> int:
        if name not in self._tab_dict:
            raise ValueError(f"Unknown tab: {name}")
        return self._name_list.index(name)

    def set(self, name: str) -> None:
        if name not in self._tab_dict:
            raise ValueError(f"Unknown tab: {name}")
        if self._current_name == name:
            if self._segmented_button.get() != name:
                self._segmented_button.set(name)
            return
        old_name = self._current_name
        self._current_name = name
        if self._segmented_button.get() != name:
            self._segmented_button.set(name)
        self._switch_tab_visibility(old_name, name)

    def get(self) -> str:
        return self._current_name

    def winfo_children(self) -> list[Any]:
        # CTkTabview exposes its tab frames, not its internal canvas or
        # segmented control, through standard child introspection.
        return list(self._tab_dict.values()) if hasattr(self, "_tab_dict") else []

    def delete(self, name: str) -> None:
        if name not in self._tab_dict:
            raise ValueError(f"Unknown tab: {name}")
        was_current = self._current_name == name
        self._tab_dict.pop(name).destroy()
        self._name_list.remove(name)
        self._segmented_button.configure(values=self._name_list)
        if was_current:
            self._current_name = self._name_list[0] if self._name_list else ""
            if self._current_name:
                self._segmented_button.set(self._current_name)
                self._switch_tab_visibility("", self._current_name)

    def move(self, first: int, second: int | str) -> None:
        if isinstance(second, int):
            super().move(first, second)
            self._layout_internal_parts()
            return
        if second not in self._name_list:
            raise ValueError(f"Unknown tab: {second}")
        self._name_list.remove(second)
        self._name_list.insert(first, second)
        self._segmented_button.configure(values=self._name_list)
        if self._current_name:
            self._segmented_button.set(self._current_name)

    def rename(self, old_name: str, new_name: str) -> None:
        self.rename_tab(old_name, new_name)

    def rename_tab(self, old_name: str, new_name: str) -> None:
        if old_name not in self._tab_dict:
            raise ValueError(f"Unknown tab: {old_name}")
        if new_name in self._tab_dict:
            raise ValueError(f"Tab already exists: {new_name}")
        index = self._name_list.index(old_name)
        frame = self._tab_dict.pop(old_name)
        self._tab_dict[new_name] = frame
        self._name_list[index] = new_name
        if self._current_name == old_name:
            self._current_name = new_name
        self._segmented_button.configure(values=self._name_list)
        if self._current_name:
            self._segmented_button.set(self._current_name)

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        layout_changed = "width" in kwargs or "height" in kwargs
        segmented_options = {
            "segmented_button_fg_color": "fg_color",
            "segmented_button_selected_color": "selected_color",
            "segmented_button_selected_hover_color": "selected_hover_color",
            "segmented_button_unselected_color": "unselected_color",
            "segmented_button_unselected_hover_color": "unselected_hover_color",
            "text_color": "text_color",
            "text_color_disabled": "text_color_disabled",
            "state": "state",
        }
        updates = {target: kwargs.pop(source) for source, target in segmented_options.items() if source in kwargs}
        if updates:
            self._segmented_button.configure(**updates)
            if "state" in updates:
                self._tab_state = str(updates["state"])
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if "anchor" in kwargs:
            anchor = str(kwargs.pop("anchor"))
            if anchor != self._tab_anchor:
                self._tab_anchor = anchor
                layout_changed = True
        if "corner_radius" in kwargs:
            self._tab_corner_radius = int(kwargs["corner_radius"])
        if "border_width" in kwargs:
            self._tab_border_width = int(kwargs["border_width"])
        super().configure(require_redraw=require_redraw, **kwargs)
        if layout_changed:
            self._layout_internal_parts()

    config = configure

    def bind(
        self,
        sequence: str | None = None,
        command: Any = None,
        add: str | bool | None = None,
    ) -> None:
        raise NotImplementedError

    def cget(self, key: str) -> Any:
        """Return CTkTabview-specific options using CustomTkinter's names."""
        segmented_options = {
            "segmented_button_fg_color": "fg_color",
            "segmented_button_selected_color": "selected_color",
            "segmented_button_selected_hover_color": "selected_hover_color",
            "segmented_button_unselected_color": "unselected_color",
            "segmented_button_unselected_hover_color": "unselected_hover_color",
            "text_color": "text_color",
            "text_color_disabled": "text_color_disabled",
        }
        if key in segmented_options:
            return self._segmented_button.cget(segmented_options[key])
        if key == "command":
            return self._command
        if key == "anchor":
            return self._tab_anchor
        if key == "state":
            return self._segmented_button.cget("state")
        return super().cget(key)

    def _resize_for_place(self, width: int | None, height: int | None) -> None:
        super()._resize_for_place(width, height)
        if hasattr(self, "_content"):
            self._layout_internal_parts()

    def _on_widget_scaling_changed(self, old_scaling: float, new_scaling: float) -> None:
        super()._on_widget_scaling_changed(old_scaling, new_scaling)
        if hasattr(self, "_content"):
            self.canvas.after_idle(self._layout_internal_parts)

    def _hide(self) -> None:
        super()._hide()

    def _show(self) -> None:
        super()._show()
        if hasattr(self, "_tab_dict"):
            self._layout_internal_parts()
            self._sync_tab_visibility()

    def destroy(self) -> None:
        if hasattr(self, "_content"):
            self._content.destroy()
        super().destroy()


class _ScrollableContentFrame(Frame):
    def __init__(self, owner: "ScrollableFrame", *args: Any, **kwargs: Any) -> None:
        self._scroll_owner = owner
        super().__init__(*args, **kwargs)

    def _relayout_children(self) -> None:
        super()._relayout_children()
        if hasattr(self, "_scroll_owner"):
            self._scroll_owner._schedule_scrollregion_update()


class ScrollableFrame(Frame):
    """CanvasCTk port of ``CTkScrollableFrame`` with opacity-aware content."""

    _scrollbar_thickness = 16
    _label_height = 28

    def _packed_background_radius(self) -> int:
        return int(self._options.get("border_radius", 0) or 0)

    def _border_spacing(self) -> int:
        return max(
            0,
            int(self._options.get("border_radius", 0) or 0)
            + int(self._options.get("border_width", 0) or 0),
        )

    def _has_label(self) -> bool:
        return bool(self._label_text)

    def _desired_outer_size(self, spacing: int | None = None) -> tuple[int, int]:
        spacing = self._border_spacing() if spacing is None else max(0, int(spacing))
        scrollbar_extent = 0 if self.hide_scrollbar else self._scrollbar_thickness
        label_extent = self._label_height + spacing * 2 if self._has_label() else 0
        if self.orientation == "vertical":
            return (
                self._viewport_desired_width + spacing + scrollbar_extent,
                self._viewport_desired_height + spacing * 2 + label_extent,
            )
        return (
            self._viewport_desired_width + spacing * 2,
            self._viewport_desired_height + spacing + scrollbar_extent + label_extent,
        )

    def __init__(
        self,
        master: Any,
        width: int = 200,
        height: int = 200,
        corner_radius: int | None = None,
        border_width: int | None = None,
        bg_color: Any = "transparent",
        fg_color: Any = None,
        border_color: Any = None,
        scrollbar_fg_color: Any = None,
        scrollbar_button_color: Any = None,
        scrollbar_button_hover_color: Any = None,
        label_fg_color: Any = None,
        label_text_color: Any = None,
        label_text: str = "",
        label_font: Any = None,
        label_anchor: str = "center",
        orientation: str = "vertical",
        *,
        hide_scrollbar: bool = False,
        **kwargs: Any,
    ) -> None:
        self.orientation = str(orientation).lower()
        if self.orientation not in {"vertical", "horizontal"}:
            raise ValueError("orientation must be 'vertical' or 'horizontal'")
        self.hide_scrollbar = bool(hide_scrollbar)
        self._viewport_desired_width = max(1, int(width))
        self._viewport_desired_height = max(1, int(height))
        self._label_text = "" if label_text is None else str(label_text)
        self._scrollregion_pending = False
        self._updating_viewport = False
        self._scroll_offset = 0
        self._uses_shared_viewport = False
        frame_theme = ctk.ThemeManager.theme["CTkFrame"]
        initial_radius = int(frame_theme["corner_radius"] if corner_radius is None else corner_radius)
        initial_border_width = int(frame_theme["border_width"] if border_width is None else border_width)
        outer_width, outer_height = self._desired_outer_size(initial_radius + initial_border_width)
        super().__init__(
            master,
            width=outer_width,
            height=outer_height,
            bg_color=bg_color,
            fg_color=fg_color,
            corner_radius=corner_radius,
            border_width=border_width,
            border_color=border_color,
            **kwargs,
        )
        active_fg = _appearance_color(self._options.get("fg_color"), "transparent").lower()
        self._uses_shared_viewport = (
            float(self._options.get("opacity", 1)) < 1
            or float(self._options.get("bg_opacity", 1)) < 1
            or self._options.get("image") is not None
            or active_fg in {"transparent", "#00000000"}
        )
        if self._uses_shared_viewport:
            # A Tk Canvas child window is always opaque.  Draw translucent and
            # image-backed scrollable content on the parent's canvas so labels
            # with fg_color="transparent" reveal the actual pixels underneath.
            self._content_canvas = self.canvas
        else:
            self._content_canvas = ctk.CTkCanvas(self.canvas, highlightthickness=0, bd=0)
            self._viewport_window = self.canvas.create_window(
                0,
                0,
                window=self._content_canvas,
                anchor="nw",
                state="hidden",
            )
        scrollable_theme = ctk.ThemeManager.theme["CTkScrollableFrame"]
        self._track_theme_defaults(
            "CTkScrollableFrame",
            label_fg_color="label_fg_color" if label_fg_color is None else False,
        )
        self._track_theme_defaults(
            "CTkScrollbar",
            scrollbar_fg_color="fg_color" if scrollbar_fg_color is None else False,
            scrollbar_button_color="button_color" if scrollbar_button_color is None else False,
            scrollbar_button_hover_color="button_hover_color" if scrollbar_button_hover_color is None else False,
        )
        self._track_theme_defaults(
            "CTkLabel",
            label_text_color="text_color" if label_text_color is None else False,
        )
        self._label = self.put(Label(
            self,
            canvas=self.canvas,
            width=max(1, self._width - self._border_spacing() * 2),
            height=self._label_height,
            corner_radius=self._options.get("border_radius", 0),
            fg_color=scrollable_theme["label_fg_color"] if label_fg_color is None else label_fg_color,
            text_color=label_text_color,
            text=self._label_text,
            font=label_font,
            anchor=label_anchor,
        ))
        if not self._label_text:
            self._label.hide()
        self._content = _ScrollableContentFrame(
            self,
            self,
            canvas=self._content_canvas,
            width=1,
            height=None,
            fg_color="transparent",
        )
        self._content.show()
        self._scrollbar = self.put(Scrollbar(
            self,
            canvas=self.canvas,
            width=self._scrollbar_thickness if self.orientation == "vertical" else self._width,
            height=self._viewport_desired_height if self.orientation == "vertical" else self._scrollbar_thickness,
            orientation=self.orientation,
            fg_color=scrollbar_fg_color,
            button_color=scrollbar_button_color,
            button_hover_color=scrollbar_button_hover_color,
            command=self._scrollbar_command,
        ))
        self._scrollbar.hide()
        if not self._uses_shared_viewport:
            self._content_canvas.bind("<Configure>", lambda _event: self._update_scrollregion(), add="+")
            self._content_canvas.bind("<MouseWheel>", self._on_mousewheel, add="+")
            self._content_canvas.bind("<Button-4>", lambda event: self._on_mousewheel(event, -120), add="+")
            self._content_canvas.bind("<Button-5>", lambda event: self._on_mousewheel(event, 120), add="+")
        self.canvas.bind("<MouseWheel>", self._on_mousewheel, add="+")
        self._layout_viewport()

    def _resolved_viewport_color(self) -> Any:
        color = self.cget("fg_color")
        if color in (None, "transparent"):
            color = self.canvas.cget("bg")
        if isinstance(color, (tuple, list)):
            return color[1 if ctk.get_appearance_mode() == "Dark" else 0]
        return color

    def _viewport_geometry(self) -> tuple[int, int, int, int]:
        spacing = self._border_spacing()
        left, top = self._origin()
        scrollbar_extent = 0 if self.hide_scrollbar else self._scrollbar_thickness
        label_extent = self._label_height + spacing * 2 if self._has_label() else 0
        if self.orientation == "vertical":
            return (
                left + spacing,
                top + spacing + label_extent,
                max(1, self._width - spacing - scrollbar_extent),
                max(1, self._height - spacing * 2 - label_extent),
            )
        return (
            left + spacing,
            top + spacing + label_extent,
            max(1, self._width - spacing * 2),
            max(1, self._height - spacing - label_extent - scrollbar_extent),
        )

    def _layout_label(self) -> None:
        if not hasattr(self, "_label"):
            return
        if not self._label_text:
            self._label.hide()
            return
        spacing = self._border_spacing()
        left, top = self._origin()
        label_width = max(1, self._width - spacing * 2)
        if self._label._width != label_width or self._label._height != self._label_height:
            self._label.configure(width=label_width, height=self._label_height)
        corner_radius = self._options.get("border_radius", 0)
        if self._label.cget("corner_radius") != corner_radius:
            self._label.configure(corner_radius=corner_radius)
        label_x = left + spacing + label_width / 2
        label_y = top + spacing + self._label_height / 2
        if self._label._x != int(label_x) or self._label._y != int(label_y):
            self._label.move(label_x, label_y)
        if self._is_rendered:
            self._label.show()

    def _is_effectively_rendered(self) -> bool:
        current: Any = self
        while isinstance(current, Item):
            if not bool(getattr(current, "_is_rendered", False)):
                return False
            current = getattr(current, "_canvas_host", None)
        return True

    def _shared_content_origin(self) -> tuple[int, int]:
        x, y, _, _ = self._viewport_geometry()
        if self.orientation == "vertical":
            y -= self._scroll_offset
        else:
            x -= self._scroll_offset
        return x, y

    def _apply_shared_viewport_visibility(self) -> None:
        if not self._uses_shared_viewport or not hasattr(self, "_content"):
            return
        viewport_x, viewport_y, viewport_width, viewport_height = self._viewport_geometry()
        viewport_right = viewport_x + viewport_width
        viewport_bottom = viewport_y + viewport_height
        may_render = self._is_effectively_rendered()
        for widget in tuple(self._content._child_widgets):
            if isinstance(widget, Item):
                left, top = widget._winfo_origin()
                right = left + widget._width
                bottom = top + widget._height
            else:
                window_id = self._content._child_windows.get(widget)
                bounds = None if window_id is None else self.canvas.bbox(window_id)
                if bounds is None:
                    continue
                left = self._reverse_widget_scaling(bounds[0])
                top = self._reverse_widget_scaling(bounds[1])
                right = self._reverse_widget_scaling(bounds[2])
                bottom = self._reverse_widget_scaling(bounds[3])
            if self.orientation == "vertical":
                visible = (
                    may_render
                    and right > viewport_x
                    and left < viewport_right
                    and top >= viewport_y - 1
                    and bottom <= viewport_bottom + 1
                )
            else:
                visible = (
                    may_render
                    and bottom > viewport_y
                    and top < viewport_bottom
                    and left >= viewport_x - 1
                    and right <= viewport_right + 1
                )
            clipped = bool(getattr(widget, "_canvasctk_viewport_clipped", False))
            if not visible:
                if not clipped:
                    widget._canvasctk_viewport_was_hidden = bool(getattr(widget, "is_hidden", False))
                    widget._canvasctk_viewport_clipped = True
                self._content._hide_child_widget(widget)
            elif clipped:
                was_hidden = bool(getattr(widget, "_canvasctk_viewport_was_hidden", False))
                widget._canvasctk_viewport_clipped = False
                if isinstance(widget, Item):
                    widget.is_hidden = was_hidden
                if was_hidden:
                    self._content._hide_child_widget(widget)
                else:
                    self._content._show_child_widget(widget)

    def _position_shared_content(self) -> None:
        if not self._uses_shared_viewport or not hasattr(self, "_content"):
            return
        x, y = self._shared_content_origin()
        if self._content._x != x or self._content._y != y:
            self._content.move(x, y)
            self._content._relayout_children()
        self._apply_shared_viewport_visibility()

    def _layout_viewport(self) -> None:
        if not hasattr(self, "_content_canvas") or self._updating_viewport:
            return
        self._updating_viewport = True
        try:
            self._layout_label()
            x, y, width, height = self._viewport_geometry()
            physical_x, physical_y = self._physical_point(x, y)
            physical_width = max(1, int(round(self._apply_widget_scaling(width))))
            physical_height = max(1, int(round(self._apply_widget_scaling(height))))
            if self._uses_shared_viewport:
                self._position_shared_content()
            else:
                self._content_canvas.configure(width=physical_width, height=physical_height, bg=self._resolved_viewport_color())
                self.canvas.coords(self._viewport_window, physical_x, physical_y)
                self.canvas.itemconfigure(
                    self._viewport_window,
                    width=physical_width,
                    height=physical_height,
                    state="normal" if self._is_effectively_rendered() else "hidden",
                )
            if self.orientation == "vertical":
                if self._content.cget("width") != width:
                    self._content.configure(width=width)
                if self._scrollbar._height != height:
                    self._scrollbar.configure(height=height)
                scrollbar_x = x + width + self._scrollbar_thickness / 2
                scrollbar_y = y + height / 2
                if self._scrollbar._x != int(scrollbar_x) or self._scrollbar._y != int(scrollbar_y):
                    self._scrollbar.move(scrollbar_x, scrollbar_y)
            else:
                if self._content.cget("height") != height:
                    self._content.configure(height=height)
                if self._scrollbar._width != width:
                    self._scrollbar.configure(width=width)
                scrollbar_x = x + width / 2
                scrollbar_y = y + height + self._scrollbar_thickness / 2
                if self._scrollbar._x != int(scrollbar_x) or self._scrollbar._y != int(scrollbar_y):
                    self._scrollbar.move(scrollbar_x, scrollbar_y)
        finally:
            self._updating_viewport = False
        self._update_scrollregion()

    def _on_widget_scaling_changed(self, old_scaling: float, new_scaling: float) -> None:
        super()._on_widget_scaling_changed(old_scaling, new_scaling)
        if hasattr(self, "_content_canvas"):
            self.canvas.after_idle(self._layout_viewport)

    def _schedule_scrollregion_update(self) -> None:
        if self._scrollregion_pending or not hasattr(self, "_content_canvas"):
            return
        self._scrollregion_pending = True
        self._content_canvas.after_idle(self._flush_scrollregion_update)

    def _flush_scrollregion_update(self) -> None:
        self._scrollregion_pending = False
        if not self._destroyed:
            self._update_scrollregion()

    def _update_scrollregion(self) -> None:
        if not hasattr(self, "_content_canvas") or self._updating_viewport:
            return
        _, _, viewport_width, viewport_height = self._viewport_geometry()
        content_width = max(viewport_width, self._content._width)
        content_height = max(viewport_height, self._content._height)
        self._content_extent = content_height if self.orientation == "vertical" else content_width
        if self._uses_shared_viewport:
            viewport = viewport_height if self.orientation == "vertical" else viewport_width
            maximum = max(0, self._content_extent - viewport)
            self._scroll_offset = max(0, min(self._scroll_offset, maximum))
            first = 0.0 if self._content_extent <= 0 else self._scroll_offset / self._content_extent
            last = 1.0 if self._content_extent <= 0 else min(1.0, (self._scroll_offset + viewport) / self._content_extent)
            self._position_shared_content()
        else:
            self._content_canvas.configure(
                scrollregion=(
                    0,
                    0,
                    self._apply_widget_scaling(content_width),
                    self._apply_widget_scaling(content_height),
                )
            )
            first, last = self._content_canvas.yview() if self.orientation == "vertical" else self._content_canvas.xview()
        self._scrollbar.set(first, last)
        if self.hide_scrollbar:
            self._scrollbar.hide()
        elif self._is_effectively_rendered():
            self._scrollbar.show()
            self.canvas.tag_raise(self._scrollbar._canvas._root_tag)
        else:
            # An idle scroll-region update can run after an ancestor tab has
            # hidden this frame.  ``is_hidden`` intentionally preserves the
            # child's own requested visibility across that transition, so it
            # cannot be used to decide whether canvas items may be revealed.
            self._scrollbar.hide()

    def _pointer_inside(self) -> bool:
        px = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
        py = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
        px = self._reverse_widget_scaling(px)
        py = self._reverse_widget_scaling(py)
        left, top = self._origin()
        return left <= px <= left + self._width and top <= py <= top + self._height

    def _on_mousewheel(self, event: Any, delta: int | None = None) -> None:
        if not self._pointer_inside():
            return
        wheel_delta = int(delta if delta is not None else getattr(event, "delta", 0))
        steps = int(-wheel_delta / 120) if wheel_delta else 0
        if not steps:
            return
        if self._uses_shared_viewport:
            self._scroll_offset += steps * 24
        elif self.orientation == "vertical":
            self._content_canvas.yview_scroll(steps, "units")
        else:
            self._content_canvas.xview_scroll(steps, "units")
        self._update_scrollregion()

    def _scrollbar_command(self, action: str, value: Any, units: Any = None) -> None:
        if self._uses_shared_viewport:
            _, _, viewport_width, viewport_height = self._viewport_geometry()
            viewport = viewport_height if self.orientation == "vertical" else viewport_width
            maximum = max(0, self._content_extent - viewport)
            if action == "moveto":
                self._scroll_offset = round(maximum * max(0.0, min(1.0, float(value))))
            elif action == "scroll":
                increment = viewport if str(units or "units") == "pages" else 24
                self._scroll_offset += int(value) * increment
            self._update_scrollregion()
            return
        view = self._content_canvas.yview if self.orientation == "vertical" else self._content_canvas.xview
        if action == "moveto":
            view("moveto", value)
        elif action == "scroll":
            view("scroll", value, units or "units")
        self._update_scrollregion()

    def scroll_to(self, fraction: float) -> None:
        fraction = max(0.0, min(1.0, float(fraction)))
        if self._uses_shared_viewport:
            _, _, viewport_width, viewport_height = self._viewport_geometry()
            viewport = viewport_height if self.orientation == "vertical" else viewport_width
            self._scroll_offset = round(max(0, self._content_extent - viewport) * fraction)
        elif self.orientation == "vertical":
            self._content_canvas.yview_moveto(fraction)
        else:
            self._content_canvas.xview_moveto(fraction)
        self._update_scrollregion()
        _, _, viewport_width, viewport_height = self._viewport_geometry()
        viewport = viewport_height if self.orientation == "vertical" else viewport_width
        self._scroll_offset = round(max(0, self._content_extent - viewport) * fraction)

    def _attach_child_item(self, widget: Item, manager: str, options: dict[str, Any]) -> None:
        self._content._attach_child_item(widget, manager, options)

    def _attach_child_widget(self, widget: Any, manager: str, options: dict[str, Any]) -> None:
        """Manage native Tk/CTk children in the scrollable content viewport."""
        self._content._attach_child_widget(widget, manager, options)

    def _validate_child_manager(self, widget: Any, manager: str) -> None:
        if hasattr(self, "_content"):
            self._content._validate_child_manager(widget, manager)
        else:
            super()._validate_child_manager(widget, manager)

    def _next_implicit_grid_row(self, widget: Any = None) -> int:
        # Geometry-managed children live on ``_content``.  Looking at this
        # outer frame's layout table always returned zero, causing every
        # argument-less ``child.grid()`` to overlap in the first row.
        if hasattr(self, "_content"):
            return self._content._next_implicit_grid_row(widget)
        return super()._next_implicit_grid_row(widget)

    def _forget_child_widget(self, widget: Any, hide: bool = True) -> None:
        self._content._forget_child_widget(widget, hide=hide)

    def _detach_child_widget(self, widget: Any) -> None:
        self._content._detach_child_widget(widget)

    def winfo_reqwidth(self) -> int:
        return self._content.winfo_reqwidth()

    def winfo_reqheight(self) -> int:
        return self._content.winfo_reqheight()

    def winfo_children(self) -> list[Any]:
        return self._content.winfo_children()

    def grid_slaves(self, row: int | None = None, column: int | None = None) -> list[Any]:
        return self._content.grid_slaves(row=row, column=column)

    def pack_slaves(self) -> list[Any]:
        return self._content.pack_slaves()

    def place_slaves(self) -> list[Any]:
        return self._content.place_slaves()

    def grid_columnconfigure(self, index: Any, cnf: Any = None, **kwargs: Any) -> Any:
        return self._content.grid_columnconfigure(index, cnf, **kwargs)

    columnconfigure = grid_columnconfigure

    def grid_rowconfigure(self, index: Any, cnf: Any = None, **kwargs: Any) -> Any:
        return self._content.grid_rowconfigure(index, cnf, **kwargs)

    rowconfigure = grid_rowconfigure

    def grid_size(self) -> tuple[int, int]:
        return self._content.grid_size()

    def grid_bbox(
        self,
        column: int | None = None,
        row: int | None = None,
        col2: int | None = None,
        row2: int | None = None,
    ) -> tuple[int, int, int, int]:
        return self._content.grid_bbox(column, row, col2, row2)

    def grid_location(self, x: int, y: int) -> tuple[int, int]:
        return self._content.grid_location(x, y)

    def pack_propagate(self, flag: Any = tk.Misc._noarg_) -> bool | None:
        return self._content.pack_propagate(flag)

    propagate = pack_propagate

    def grid_propagate(self, flag: Any = tk.Misc._noarg_) -> bool | None:
        return self._content.grid_propagate(flag)

    def configure(self, **kwargs: Any) -> None:
        label_updates: dict[str, Any] = {}
        scrollbar_options: dict[str, Any] = {}
        layout_changed = False
        if "width" in kwargs:
            width = max(1, int(kwargs.pop("width")))
            if width != self._viewport_desired_width:
                self._viewport_desired_width = width
                layout_changed = True
        if "height" in kwargs:
            height = max(1, int(kwargs.pop("height")))
            if height != self._viewport_desired_height:
                self._viewport_desired_height = height
                layout_changed = True
        if "label_text" in kwargs:
            label_text = kwargs.pop("label_text")
            label_text = "" if label_text is None else str(label_text)
            if label_text != self._label_text:
                self._label_text = label_text
                label_updates["text"] = label_text
                layout_changed = True
        for source, target in {
            "label_font": "font",
            "label_text_color": "text_color",
            "label_fg_color": "fg_color",
            "label_anchor": "anchor",
        }.items():
            if source in kwargs:
                value = kwargs.pop(source)
                if self._label.cget(target) != value:
                    label_updates[target] = value
        scrollbar_updates = {
            "scrollbar_fg_color": "fg_color",
            "scrollbar_button_color": "button_color",
            "scrollbar_button_hover_color": "button_hover_color",
        }
        for source, target in scrollbar_updates.items():
            if source in kwargs:
                value = kwargs.pop(source)
                if self._scrollbar.cget(target) != value:
                    scrollbar_options[target] = value
        for option in ("corner_radius", "border_radius", "border_width"):
            if option in kwargs:
                current_key = "border_radius" if option == "corner_radius" else option
                if self._options.get(current_key) != kwargs[option]:
                    layout_changed = True
        if layout_changed:
            radius = int(kwargs.get("corner_radius", kwargs.get("border_radius", self._options.get("border_radius", 0))) or 0)
            border_width = int(kwargs.get("border_width", self._options.get("border_width", 0)) or 0)
            outer_width, outer_height = self._desired_outer_size(radius + border_width)
            kwargs["width"] = outer_width
            kwargs["height"] = outer_height
        if kwargs:
            super().configure(**kwargs)
        if label_updates:
            self._label.configure(**label_updates)
        if scrollbar_options:
            self._scrollbar.configure(**scrollbar_options)
        if layout_changed:
            self._layout_viewport()

    config = configure

    def cget(self, key: str) -> Any:
        values = {
            "width": self._viewport_desired_width,
            "height": self._viewport_desired_height,
            "label_text": self._label_text,
            "label_font": self._label.cget("font"),
            "label_text_color": self._label.cget("text_color"),
            "label_fg_color": self._label.cget("fg_color"),
            "label_anchor": self._label.cget("anchor"),
            "scrollbar_fg_color": self._scrollbar.cget("fg_color"),
            "scrollbar_button_color": self._scrollbar.cget("button_color"),
            "scrollbar_button_hover_color": self._scrollbar.cget("button_hover_color"),
        }
        return values[key] if key in values else super().cget(key)

    def bind(
        self,
        sequence: str | None = None,
        func: Any = None,
        add: str | bool | None = None,
    ) -> str | None:
        if self._is_lifecycle_event(sequence):
            return self._bind_lifecycle_event(sequence, func, add)
        if func is None:
            return self._content_canvas.bind(sequence, None, add)
        frame_add = add if add in ("+", True) else True
        frame_result = super().bind(sequence, func, frame_add)
        content_result = (
            frame_result
            if self._uses_shared_viewport
            else self._content_canvas.bind(sequence, func, add=add)
        )
        logical_add = add if add in ("+", True) else True
        self._label.bind(sequence, func, add=logical_add)
        self._scrollbar.bind(sequence, func, add=logical_add)
        return content_result

    def unbind(self, sequence: str, funcid: str | None = None) -> None:
        if self._is_lifecycle_event(sequence):
            self._unbind_lifecycle_event(sequence, funcid)
            return
        if funcid is None:
            super().unbind(sequence)
        if funcid is None and not self._uses_shared_viewport:
            self._content_canvas.unbind(sequence)
            self._label.unbind(sequence)
            self._scrollbar.unbind(sequence)
        elif funcid is not None and not self._uses_shared_viewport:
            self._content_canvas.unbind(sequence, funcid)

    def _resize_for_place(self, width: int | None, height: int | None) -> None:
        super()._resize_for_place(width, height)
        self._layout_viewport()

    def move(self, x: int, y: int) -> None:
        super().move(x, y)
        self._layout_viewport()

    def _hide(self) -> None:
        super()._hide()
        if hasattr(self, "_scrollbar"):
            self._scrollbar.hide()
        if hasattr(self, "_label"):
            self._label.hide()
        if getattr(self, "_uses_shared_viewport", False) and hasattr(self, "_content"):
            self._content.hide()
            self._apply_shared_viewport_visibility()
        elif hasattr(self, "_viewport_window"):
            self.canvas.itemconfigure(self._viewport_window, state="hidden")
            self._content.hide()

    def _show(self) -> None:
        super()._show()
        if getattr(self, "_uses_shared_viewport", False) and hasattr(self, "_content"):
            self._content.show()
            self._layout_viewport()
            self._schedule_visible_scrollbar_refresh()
        elif hasattr(self, "_viewport_window"):
            self.canvas.itemconfigure(
                self._viewport_window,
                state="normal" if self._is_effectively_rendered() else "hidden",
            )
            self._content.show()
            self._layout_viewport()
            self._schedule_visible_scrollbar_refresh()

    def _schedule_visible_scrollbar_refresh(self) -> None:
        if not hasattr(self, "_content_canvas"):
            return

        def refresh() -> None:
            if self._destroyed:
                return
            if self._is_effectively_rendered():
                self._layout_viewport()
            elif hasattr(self, "_scrollbar"):
                self._scrollbar.hide()

        self.canvas.after_idle(refresh)

    def destroy(self) -> None:
        if hasattr(self, "_content"):
            self._content.destroy()
        if hasattr(self, "_viewport_window"):
            try:
                self.canvas.delete(self._viewport_window)
            except Exception:
                pass
        if hasattr(self, "_content_canvas") and not getattr(self, "_uses_shared_viewport", False):
            try:
                self._content_canvas.destroy()
            except Exception:
                pass
        super().destroy()
