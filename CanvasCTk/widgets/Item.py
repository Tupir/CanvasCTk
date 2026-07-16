from ._shared import *
from customtkinter.windows.widgets.scaling.scaling_tracker import ScalingTracker
from .._identity_registry import IdentityRegistry

class Item(Element):
    """Base for items drawn directly on a Frame canvas."""

    def __init__(self, master: Any, canvas: tk.Canvas | None = None, **kwargs: Any) -> None:
        Element.__init__(self, **kwargs)
        self.is_hidden = True
        self.master = master
        self.canvas = canvas or getattr(master, "_content_canvas", None) or master.canvas
        self.tk = self.canvas.tk
        self._w = self.canvas._w
        self.children = self.canvas.children
        if getattr(self.canvas, "_last_child_ids", None) is None:
            self.canvas._last_child_ids = {}
        self._last_child_ids = self.canvas._last_child_ids
        self._canvas_host = master if hasattr(master, "_attach_child_item") else None
        self._layout_host: Any = None
        self._layout_host_destroy_binding: tuple[Any, str] | None = None
        self._x = 0
        self._y = 0
        self._width = 0
        self._height = 0
        self._anchor = "center"
        self._layout_manager = ""
        self._layout_options: dict[str, Any] = {}
        self._grid_remove_options: dict[str, Any] | None = None
        self._is_rendered = False
        self._show_requested = False
        self._ensure_canvas_dispatchers()
        self._widget_scaling = float(
            getattr(self.canvas, "_canvasctk_widget_scaling", ScalingTracker.widget_scaling)
        )
        self._window_scaling = float(
            getattr(self.canvas, "_canvasctk_window_scaling", ScalingTracker.window_scaling)
        )
        self._retain_canvas_item()
        # Geometry may later be delegated with ``in_``, but Tk keeps the
        # construction parent as the widget's ownership/lifecycle parent.
        # Register that relationship independently from geometry ownership.
        if self._canvas_host is not None and hasattr(self._canvas_host, "put"):
            self._canvas_host.put(self)

    def _ensure_canvas_dispatchers(self) -> None:
        canvas = self.canvas
        refs = getattr(canvas, "_canvas_ui_item_refs", None)
        if not isinstance(refs, IdentityRegistry):
            refs = IdentityRegistry(() if refs is None else tuple(refs))
            canvas._canvas_ui_item_refs = refs

        widgets = getattr(canvas, "_canvas_ui_widgets", None)
        if widgets is not None and not isinstance(widgets, IdentityRegistry):
            canvas._canvas_ui_widgets = IdentityRegistry(tuple(widgets))

        if getattr(canvas, "_canvasctk_scaling_dispatcher", None) is None:
            try:
                widget_scaling = float(ScalingTracker.get_widget_scaling(canvas))
                window_scaling = float(ScalingTracker.get_window_scaling(canvas))
            except (AttributeError, KeyError, TypeError):
                widget_scaling = float(ScalingTracker.widget_scaling)
                window_scaling = float(ScalingTracker.window_scaling)
            canvas._canvasctk_widget_scaling = widget_scaling
            canvas._canvasctk_window_scaling = window_scaling

            def dispatch_scaling(new_widget_scaling: float, new_window_scaling: float) -> None:
                canvas._canvasctk_widget_scaling = float(new_widget_scaling)
                canvas._canvasctk_window_scaling = float(new_window_scaling)
                registry = getattr(canvas, "_canvas_ui_item_refs", ())
                for item in tuple(registry):
                    if not getattr(item, "_destroyed", False):
                        item._set_scaling(new_widget_scaling, new_window_scaling)

            canvas._canvasctk_scaling_dispatcher = dispatch_scaling
            ScalingTracker.add_widget(dispatch_scaling, canvas)

        if getattr(canvas, "_canvasctk_destroy_dispatcher_id", None) is None:
            def dispatch_destroy(event: Any = None) -> None:
                if event is not None and getattr(event, "widget", canvas) is not canvas:
                    return
                canvas._canvasctk_dispatching_destroy = True
                registry = getattr(canvas, "_canvas_ui_item_refs", ())
                try:
                    for item in tuple(registry):
                        item._on_canvas_destroy(event)
                finally:
                    try:
                        registry.clear()
                    except AttributeError:
                        pass
                    layout_registry = getattr(canvas, "_canvas_ui_widgets", None)
                    if layout_registry is not None:
                        try:
                            layout_registry.clear()
                        except AttributeError:
                            pass
                    Item._remove_canvas_scaling_dispatcher(canvas)
                    canvas._canvasctk_dispatching_destroy = False
                    canvas._canvasctk_destroy_dispatcher_id = None
                    canvas._canvasctk_destroy_dispatcher = None
                    canvas._canvasctk_layout_dispatcher_id = None
                    canvas._canvasctk_layout_dispatcher = None
                    canvas._canvasctk_map_dispatcher_id = None
                    canvas._canvasctk_unmap_dispatcher_id = None

            canvas._canvasctk_destroy_dispatcher = dispatch_destroy
            canvas._canvasctk_destroy_dispatcher_id = canvas.bind(
                "<Destroy>", dispatch_destroy, add="+"
            )

        if getattr(canvas, "_canvasctk_map_dispatcher_id", None) is None:
            def dispatch_map(event: Any = None) -> None:
                if event is not None and getattr(event, "widget", canvas) is not canvas:
                    return
                if getattr(canvas, "_canvasctk_layout_pending", False):
                    canvas._canvasctk_layout_pending = False
                    registry = getattr(canvas, "_canvas_ui_widgets", ())
                    layout_item = next(iter(registry), None)
                    if layout_item is not None and not getattr(layout_item, "_destroyed", False):
                        layout_item._relayout_canvas()
                for item in tuple(getattr(canvas, "_canvas_ui_item_refs", ())):
                    if (
                        not getattr(item, "_destroyed", False)
                        and getattr(item, "_show_requested", False)
                        and not getattr(item, "is_hidden", False)
                    ):
                        item.show()

            canvas._canvasctk_map_dispatcher = dispatch_map
            canvas._canvasctk_map_dispatcher_id = canvas.bind("<Map>", dispatch_map, add="+")

        if getattr(canvas, "_canvasctk_unmap_dispatcher_id", None) is None:
            def dispatch_unmap(event: Any = None) -> None:
                if event is not None and getattr(event, "widget", canvas) is not canvas:
                    return
                for item in tuple(getattr(canvas, "_canvas_ui_item_refs", ())):
                    if not getattr(item, "_destroyed", False) and getattr(item, "_is_rendered", False):
                        item._is_rendered = False
                        item._hide()

            canvas._canvasctk_unmap_dispatcher = dispatch_unmap
            canvas._canvasctk_unmap_dispatcher_id = canvas.bind("<Unmap>", dispatch_unmap, add="+")

    @staticmethod
    def _remove_canvas_scaling_dispatcher(canvas: Any) -> None:
        dispatcher = getattr(canvas, "_canvasctk_scaling_dispatcher", None)
        if dispatcher is None:
            return
        try:
            ScalingTracker.remove_widget(dispatcher, canvas)
        except Exception:
            pass
        canvas._canvasctk_scaling_dispatcher = None

    @staticmethod
    def _teardown_empty_canvas_dispatchers(canvas: Any) -> None:
        if getattr(canvas, "_canvasctk_dispatching_destroy", False):
            return
        refs = getattr(canvas, "_canvas_ui_item_refs", ())
        if refs:
            return
        Item._remove_canvas_scaling_dispatcher(canvas)
        # Keep the canvas-level Tk bindings for the canvas lifetime. Removing
        # individual Tcl commands here can make Tk delete them a second time
        # during Canvas.destroy(), and recreating them would violate the
        # one-dispatcher-per-canvas invariant.
        layout_registry = getattr(canvas, "_canvas_ui_widgets", None)
        if layout_registry is not None:
            try:
                layout_registry.clear()
            except AttributeError:
                pass

    def _set_scaling(self, new_widget_scaling: float, new_window_scaling: float) -> None:
        old_widget_scaling = self._widget_scaling
        self._widget_scaling = float(new_widget_scaling)
        self._window_scaling = float(new_window_scaling)
        self._on_widget_scaling_changed(old_widget_scaling, self._widget_scaling)

    def _on_widget_scaling_changed(self, old_scaling: float, new_scaling: float) -> None:
        if self._canvas_host is not None:
            self._canvas_host._schedule_child_layout()
        elif self._layout_manager:
            self._schedule_canvas_layout()

    def _schedule_canvas_layout(self) -> None:
        """Coalesce top-level logical geometry into one idle pass per canvas."""
        canvas = self.canvas
        if getattr(canvas, "_canvasctk_layout_pending", False):
            return
        canvas._canvasctk_layout_pending = True

        def flush_layout() -> None:
            canvas._canvasctk_layout_pending = False
            registry = getattr(canvas, "_canvas_ui_widgets", ())
            item = next(iter(registry), None)
            if item is not None and not getattr(item, "_destroyed", False):
                item._relayout_canvas()

        canvas._canvasctk_layout_after_id = canvas.after_idle(flush_layout)

    def _apply_widget_scaling(self, value: int | float) -> float:
        """Convert a logical CustomTkinter distance to canvas pixels."""
        return float(value) * self._widget_scaling

    def _reverse_widget_scaling(self, value: int | float) -> float:
        """Convert a physical canvas distance back to logical CTk units."""
        return float(value) / max(self._widget_scaling, 1e-9)

    def _apply_font_scaling(self, font: Any) -> Any:
        """Return the pixel-sized font tuple used by native canvas text items."""
        if isinstance(font, ctk.CTkFont):
            return font.create_scaled_tuple(self._widget_scaling)
        if isinstance(font, tuple):
            if len(font) == 1:
                return font
            if 2 <= len(font) <= 6:
                return (
                    font[0],
                    -abs(round(float(font[1]) * self._widget_scaling)),
                    *font[2:],
                )
        return font

    def _physical_point(self, x: int | float, y: int | float) -> tuple[int, int]:
        return (
            int(round(self._apply_widget_scaling(x))),
            int(round(self._apply_widget_scaling(y))),
        )

    def _on_canvas_destroy(self, _event: Any = None) -> None:
        if self._destroyed:
            return
        self._emit_destroy_event()

    def _cleanup_canvas_element(self) -> None:
        layout_registry = getattr(self.canvas, "_canvas_ui_widgets", None)
        if isinstance(layout_registry, IdentityRegistry):
            layout_registry.discard(self)
        elif layout_registry is not None and self in layout_registry:
            layout_registry.remove(self)
        self._release_canvas_item()
        super()._cleanup_canvas_element()

    def after(self, *args: Any) -> Any:
        return self.canvas.after(*args)

    def after_cancel(self, *args: Any) -> Any:
        return self.canvas.after_cancel(*args)

    def after_idle(self, *args: Any) -> Any:
        return self.canvas.after_idle(*args)

    def update(self) -> None:
        self.canvas.update()

    def update_idletasks(self) -> None:
        self.canvas.update_idletasks()

    def _winfo_origin(self) -> tuple[int, int]:
        anchor = (self._anchor or "center").lower()
        west_anchors = {"w", "nw", "sw"}
        east_anchors = {"e", "ne", "se"}
        north_anchors = {"n", "ne", "nw"}
        south_anchors = {"s", "se", "sw"}
        left = self._x if anchor in west_anchors else self._x - self._width if anchor in east_anchors else self._x - self._width / 2
        top = self._y if anchor in north_anchors else self._y - self._height if anchor in south_anchors else self._y - self._height / 2
        return int(round(left)), int(round(top))

    def winfo_x(self) -> int:
        left, _ = self._winfo_origin()
        host = self._canvas_host
        if host is not None and self.canvas is getattr(host, "canvas", None):
            host_left, _ = host._origin()
            left -= host_left
        return int(round(self._apply_widget_scaling(left)))

    def winfo_y(self) -> int:
        _, top = self._winfo_origin()
        host = self._canvas_host
        if host is not None and self.canvas is getattr(host, "canvas", None):
            _, host_top = host._origin()
            top -= host_top
        return int(round(self._apply_widget_scaling(top)))

    def winfo_rootx(self) -> int:
        left, _ = self._winfo_origin()
        try:
            scroll_x = int(round(float(self.canvas.canvasx(0))))
        except (AttributeError, tk.TclError, TypeError, ValueError):
            scroll_x = 0
        return (
            int(self.canvas.winfo_rootx())
            + int(round(self._apply_widget_scaling(left)))
            - scroll_x
        )

    def winfo_rooty(self) -> int:
        _, top = self._winfo_origin()
        try:
            scroll_y = int(round(float(self.canvas.canvasy(0))))
        except (AttributeError, tk.TclError, TypeError, ValueError):
            scroll_y = 0
        return (
            int(self.canvas.winfo_rooty())
            + int(round(self._apply_widget_scaling(top)))
            - scroll_y
        )

    def winfo_width(self) -> int:
        return max(1, int(round(self._apply_widget_scaling(self._width))))

    def winfo_height(self) -> int:
        return max(1, int(round(self._apply_widget_scaling(self._height))))

    def winfo_reqwidth(self) -> int:
        return self.winfo_width()

    def winfo_reqheight(self) -> int:
        return self.winfo_height()

    def winfo_exists(self) -> bool:
        if self._destroyed:
            return False
        try:
            return bool(self.canvas.winfo_exists())
        except Exception:
            return False

    def winfo_ismapped(self) -> bool:
        try:
            return self._is_rendered and bool(self.canvas.winfo_ismapped())
        except Exception:
            return self._is_rendered

    def winfo_viewable(self) -> bool:
        try:
            return self._is_rendered and bool(self.canvas.winfo_viewable())
        except Exception:
            return self._is_rendered

    def winfo_geometry(self) -> str:
        return f"{self.winfo_width()}x{self.winfo_height()}+{self.winfo_x()}+{self.winfo_y()}"

    def winfo_children(self) -> list[Any]:
        return []

    def winfo_class(self) -> str:
        return self.__class__.__name__

    def winfo_name(self) -> str:
        return self._id or self.__class__.__name__

    def winfo_parent(self) -> str:
        return str(getattr(self.master, "_w", self.master))

    def winfo_toplevel(self) -> Any:
        return self.canvas.winfo_toplevel()

    def __str__(self) -> str:
        # Canvas items do not own a Tcl widget command. Expose the shared
        # canvas path so Tk helpers which stringify a master still receive a
        # valid, resolvable Tcl path instead of a Python object repr.
        return str(self._w)

    def __getattr__(self, name: str) -> Any:
        canvas = self.__dict__.get("canvas")
        if name.startswith("winfo_") and canvas is not None and hasattr(canvas, name):
            return getattr(canvas, name)
        raise AttributeError(f"{self.__class__.__name__!s} object has no attribute {name!r}")

    @staticmethod
    def _pad(value: Any) -> tuple[int, int]:
        if isinstance(value, (tuple, list)):
            return int(value[0]), int(value[1])
        value = int(value or 0)
        return value, value

    @staticmethod
    def _distribute_grid_space(
        sizes: list[int],
        configured: Any,
        available: int,
    ) -> None:
        """Apply Tk-style positive or negative space to weighted tracks."""
        def track_options(index: int) -> dict[str, Any]:
            if isinstance(configured, dict):
                return configured.get(index, {})
            return configured[index] if index < len(configured) else {}

        weights = [
            max(0, int(track_options(index).get("weight", 0) or 0))
            for index in range(len(sizes))
        ]
        total_weight = sum(weights)
        delta = int(available) - sum(sizes)
        if delta == 0 or total_weight == 0:
            return

        if delta > 0:
            distributed = 0
            for index, weight in enumerate(weights):
                if not weight:
                    continue
                share = delta * weight // total_weight
                sizes[index] += share
                distributed += share
            for index, weight in enumerate(weights):
                if distributed >= delta:
                    break
                if weight:
                    sizes[index] += 1
                    distributed += 1
            return

        remaining = -delta
        minimums = [
            max(
                0,
                int(track_options(index).get("minsize", 0) or 0)
                + int(track_options(index).get("pad", 0) or 0),
            )
            for index in range(len(sizes))
        ]
        while remaining > 0:
            active = [
                index for index, weight in enumerate(weights)
                if weight and sizes[index] > minimums[index]
            ]
            if not active:
                break
            active_weight = sum(weights[index] for index in active)
            reduced = 0
            budget = remaining
            for index in active:
                share = remaining * weights[index] // active_weight
                if share <= 0:
                    continue
                amount = min(share, sizes[index] - minimums[index], budget)
                sizes[index] -= amount
                reduced += amount
                budget -= amount
            if reduced == 0 or budget > 0:
                for index in active:
                    if budget <= 0:
                        break
                    if sizes[index] > minimums[index]:
                        sizes[index] -= 1
                        reduced += 1
                        budget -= 1
            if reduced == 0:
                break
            remaining -= reduced

    def _registry(self) -> IdentityRegistry["Item"]:
        if not isinstance(getattr(self.canvas, "_canvas_ui_widgets", None), IdentityRegistry):
            existing = getattr(self.canvas, "_canvas_ui_widgets", ())
            self.canvas._canvas_ui_widgets = IdentityRegistry(tuple(existing))
        if getattr(self.canvas, "_canvasctk_layout_dispatcher_id", None) is None:
            canvas = self.canvas

            def dispatch_layout(_event: Any = None) -> None:
                registry = getattr(canvas, "_canvas_ui_widgets", ())
                item = next(iter(registry), None)
                if item is not None and not getattr(item, "_destroyed", False):
                    item._relayout_canvas()

            canvas._canvasctk_layout_dispatcher = dispatch_layout
            canvas._canvasctk_layout_dispatcher_id = canvas.bind(
                "<Configure>", dispatch_layout, add="+"
            )
        return self.canvas._canvas_ui_widgets

    def _next_implicit_grid_row(self) -> int:
        """Return Tk's next automatic row for a newly gridded widget.

        ``widget.grid()`` does not mean ``row=0`` in Tk.  When the row is
        omitted, Tk places the widget below the bottom-most gridded slave.
        Keep that shorthand working for both logical Frame children and
        top-level canvas items.
        """
        host = self._layout_host if self._layout_manager else self._canvas_host
        if host is not None:
            return host._next_implicit_grid_row(self)

        bottom = 0
        for item in getattr(self.canvas, "_canvas_ui_widgets", ()):
            if item is self or item._layout_manager != "grid":
                continue
            options = item._layout_options
            bottom = max(
                bottom,
                int(options.get("row", 0)) + max(1, int(options.get("rowspan", 1))),
            )
        return bottom

    def _resolve_layout_host(self, target: Any = None) -> Any:
        """Return the logical geometry master represented by ``in_``.

        Tk keeps a widget's construction parent unchanged while allowing a
        descendant/compatible container to own its geometry.  CanvasCTk can
        mirror that directly because logical containers share one canvas.
        """
        if target is None or target is self.master:
            return self._canvas_host
        if target is self.canvas:
            return None
        target_canvas = getattr(target, "canvas", None)
        if target_canvas is self.canvas:
            if hasattr(target, "_attach_child_item"):
                return target
            return None
        if getattr(target, "_content_canvas", None) is self.canvas and hasattr(target, "_attach_child_item"):
            return target
        raise tk.TclError(f'cannot use geometry manager inside {target!s}')

    @staticmethod
    def _host_storage_candidates(host: Any) -> tuple[Any, ...]:
        """Return containers which may store a delegated host's layout.

        Scrollable containers expose geometry through the outer object but
        store children in their private content Frame.  Keeping this lookup in
        Item avoids making geometry ownership double as lifecycle ownership.
        """
        if host is None:
            return ()
        candidates = [host]
        content = getattr(host, "_content", None)
        if content is not None and content is not host:
            candidates.append(content)
        return tuple(candidates)

    def _remove_effective_host_ownership(self, host: Any) -> None:
        """Keep alternate geometry hosts from owning/destroying this item."""
        for candidate in self._host_storage_candidates(host):
            if candidate is self._canvas_host:
                continue
            identity_keys = getattr(candidate, "_element_identity_keys", None)
            elements = getattr(candidate, "elements", None)
            if not isinstance(identity_keys, dict) or not isinstance(elements, dict):
                continue
            key = identity_keys.pop(id(self), None)
            if key is not None and elements.get(key) is self:
                elements.pop(key, None)

    def _unbind_layout_host_destroy(self) -> None:
        binding = self._layout_host_destroy_binding
        self._layout_host_destroy_binding = None
        if binding is None:
            return
        host, funcid = binding
        try:
            host._unbind_lifecycle_event("<Destroy>", funcid)
        except Exception:
            pass

    def _bind_layout_host_destroy(self, host: Any) -> None:
        self._unbind_layout_host_destroy()
        if host is None or not hasattr(host, "_bind_lifecycle_event"):
            return

        def host_destroyed(_event: Any = None, expected_host: Any = host) -> None:
            if self._destroyed or self._layout_host is not expected_host:
                return
            # The host is already tearing down its registries, so only clear
            # the surviving widget's geometry state. Its construction parent
            # continues to own its lifecycle.
            self._layout_manager = ""
            self._layout_options = {}
            self._grid_remove_options = None
            self._layout_host = None
            self._layout_host_destroy_binding = None
            self.hide()

        funcid = host._bind_lifecycle_event("<Destroy>", host_destroyed, "+")
        if funcid is not None:
            self._layout_host_destroy_binding = (host, funcid)

    def _validate_layout_target(self, host: Any, manager: str, options: dict[str, Any]) -> None:
        """Validate a new target before detaching the currently valid layout."""
        if host is not None:
            host._validate_child_manager(self, manager)
            before = options.get("before")
            after = options.get("after")
            reference = before if before is not None else after
            if reference is not None:
                if manager != "pack" or reference is self:
                    raise tk.TclError("window specified for -before/-after is not packed")
                reference_layout = None
                for candidate in self._host_storage_candidates(host):
                    reference_layout = getattr(candidate, "_child_layouts", {}).get(reference)
                    if reference_layout is not None:
                        break
                if reference_layout is None or reference_layout[0] != "pack":
                    raise tk.TclError("window specified for -before/-after is not packed")
            return

        registry = self._registry()
        if manager in {"grid", "pack"}:
            conflicting = "pack" if manager == "grid" else "grid"
            if any(item is not self and item._layout_manager == conflicting for item in registry):
                raise tk.TclError(
                    f"cannot use geometry manager {manager} inside {self.canvas.winfo_name()} "
                    f"which already has slaves managed by {conflicting}"
                )
        before = options.get("before")
        after = options.get("after")
        reference = before if before is not None else after
        if reference is not None and (
            manager != "pack"
            or reference is self
            or reference not in registry
            or getattr(reference, "_layout_manager", "") != "pack"
            or getattr(reference, "_layout_host", None) is not None
        ):
            raise tk.TclError("window specified for -before/-after is not packed")

    def _detach_from_layout_host(self, host: Any, *, hide: bool = False) -> None:
        if host is not None:
            host._forget_child_widget(self, hide=hide)
            return
        registry = getattr(self.canvas, "_canvas_ui_widgets", None)
        if registry is not None and self in registry:
            registry.remove(self)

    def _retain_canvas_item(self) -> None:
        """Keep canvas item wrapper objects alive even when caller doesn't store them.

        Tk canvas image items only keep the Tcl image name, not the Python
        PhotoImage wrapper. Without a Python-side reference, images can vanish
        while text still remains visible. Layout managers kept references
        accidentally; this registry makes direct coordinate placement work too.
        """
        refs = getattr(self.canvas, "_canvas_ui_item_refs", None)
        if not isinstance(refs, IdentityRegistry):
            refs = IdentityRegistry(() if refs is None else tuple(refs))
            self.canvas._canvas_ui_item_refs = refs
        refs.add(self)

    def _release_canvas_item(self) -> None:
        refs = getattr(self.canvas, "_canvas_ui_item_refs", None)
        if isinstance(refs, IdentityRegistry):
            refs.discard(self)
        elif refs is not None and self in refs:
            refs.remove(self)
        self._teardown_empty_canvas_dispatchers(self.canvas)

    def _host_is_rendered(self) -> bool:
        host = self._layout_host if self._layout_host is not None else self._canvas_host
        if host is not None:
            return bool(getattr(host, "_is_rendered", not getattr(host, "is_hidden", False)))
        try:
            return bool(self.canvas.winfo_ismapped())
        except Exception:
            return True

    def hide(self, hide: bool = True) -> None:
        if not hide:
            self.show()
            return
        self._show_requested = False
        self._is_rendered = False
        super().hide()

    def show(self, show: bool = True) -> None:
        if self._destroyed:
            return
        if not show or not self.enabled:
            self.hide()
            return
        self._show_requested = True
        self.is_hidden = False
        alive_check = getattr(self, "_canvas_items_alive", None)
        if callable(alive_check) and not alive_check():
            self._is_rendered = False
            for element in self.elements.values():
                element._show_requested = False
                element._is_rendered = False
                try:
                    element._hide()
                except (AttributeError, tk.TclError):
                    pass
            return
        if not self._host_is_rendered():
            self._is_rendered = False
            self._hide()
            return
        self._is_rendered = True
        for element in self.elements.values():
            element.show()
        self._show()

    def _show_from_geometry(self) -> None:
        self.show()

    def _register_layout(self, manager: str, options: dict[str, Any]) -> None:
        if manager != "grid":
            self._grid_remove_options = None
        target_host = self._resolve_layout_host(options.get("in_"))
        previous_host = self._layout_host
        if self._layout_manager and previous_host is not target_host:
            self._detach_from_layout_host(previous_host, hide=False)
        self._layout_host = target_host
        if target_host is not None:
            target_host._validate_child_manager(self, manager)
            self._layout_manager = manager
            self._layout_options = options
            target_host._attach_child_item(self, manager, options)
            self._show_from_geometry()
            return None
        registry = self._registry()
        if manager in {"grid", "pack"}:
            conflicting = "pack" if manager == "grid" else "grid"
            if any(item is not self and item._layout_manager == conflicting for item in registry):
                raise tk.TclError(
                    f"cannot use geometry manager {manager} inside {self.canvas.winfo_name()} "
                    f"which already has slaves managed by {conflicting}"
                )
        if self not in registry:
            registry.append(self)
        self._layout_manager = manager
        self._layout_options = options
        self._show_from_geometry()
        self._schedule_canvas_layout()
        return None

    def grid(
        self,
        row: int | None = None,
        column: int | None = None,
        rowspan: int | None = None,
        columnspan: int | None = None,
        padx: Any = None,
        pady: Any = None,
        ipadx: Any = None,
        ipady: Any = None,
        sticky: str | None = None,
        in_: Any = None,
        **kwargs: Any,
    ) -> None:
        """Arrange this canvas item with Tk-compatible grid options."""
        if isinstance(row, Mapping):
            mapping = dict(row)
            explicit = {
                "column": column, "rowspan": rowspan, "columnspan": columnspan,
                "padx": padx, "pady": pady, "ipadx": ipadx, "ipady": ipady,
                "sticky": sticky, "in_": in_,
            }
            mapping.update({key: value for key, value in explicit.items() if value is not None})
            mapping.update(kwargs)
            return self.grid(**mapping)
        if "in" in kwargs and in_ is None:
            in_ = kwargs.pop("in")
        if kwargs:
            raise tk.TclError(f"bad option '-{next(iter(kwargs))}'")
        restoring_grid = self._layout_manager == "grid" or self._grid_remove_options is not None
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
        if self._layout_manager == "grid":
            options.update(self._layout_options)
        elif self._grid_remove_options is not None:
            options.update(self._grid_remove_options)
        if row is None and not restoring_grid:
            # Resolve the row through Item's outer-geometry helper. Container
            # subclasses (Frame/ScrollableFrame) also expose a same-named
            # helper for arranging *their children*; dynamically dispatching
            # to that override here made a nested Frame inspect its own empty
            # grid and place itself at row 0 instead of below its siblings.
            options["row"] = Item._next_implicit_grid_row(self)
        updates = {
            "row": row,
            "column": column,
            "rowspan": rowspan,
            "columnspan": columnspan,
            "padx": padx,
            "pady": pady,
            "ipadx": ipadx,
            "ipady": ipady,
            "sticky": sticky.lower() if sticky is not None else None,
            "in_": in_,
        }
        options.update({key: value for key, value in updates.items() if value is not None})
        options["row"] = int(options["row"])
        options["column"] = int(options["column"])
        if options["row"] < 0 or options["column"] < 0:
            raise tk.TclError("row and column must be non-negative")
        options["rowspan"] = int(options["rowspan"])
        options["columnspan"] = int(options["columnspan"])
        if options["rowspan"] < 1 or options["columnspan"] < 1:
            raise tk.TclError("rowspan and columnspan must be positive")
        sticky_value = str(options["sticky"]).lower()
        if any(character not in "nsew" for character in sticky_value):
            raise tk.TclError(f'bad stickyness value "{options["sticky"]}": must be a string containing n, e, s, and/or w')
        options["sticky"] = "".join(
            character for character in "nesw" if character in sticky_value
        )
        self._grid_remove_options = None
        return self._register_layout("grid", options)

    def pack(
        self,
        side: str | None = None,
        padx: Any = None,
        pady: Any = None,
        anchor: str | None = None,
        fill: str | None = None,
        expand: Any = None,
        ipadx: Any = None,
        ipady: Any = None,
        before: Any = None,
        after: Any = None,
        in_: Any = None,
        **kwargs: Any,
    ) -> None:
        """Arrange this canvas item using Tk's pack option model."""
        if isinstance(side, Mapping):
            mapping = dict(side)
            explicit = {
                "padx": padx, "pady": pady, "anchor": anchor, "fill": fill,
                "expand": expand, "ipadx": ipadx, "ipady": ipady,
                "before": before, "after": after, "in_": in_,
            }
            mapping.update({key: value for key, value in explicit.items() if value is not None})
            mapping.update(kwargs)
            return self.pack(**mapping)
        if "in" in kwargs and in_ is None:
            in_ = kwargs.pop("in")
        if kwargs:
            raise tk.TclError(f"bad option '-{next(iter(kwargs))}'")
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
        if self._layout_manager == "pack":
            options.update(self._layout_options)
        updates = {
            "side": side,
            "padx": padx,
            "pady": pady,
            "ipadx": ipadx,
            "ipady": ipady,
            "anchor": anchor,
            "fill": fill,
            "expand": expand,
            "before": before,
            "after": after,
            "in_": in_,
        }
        options.update({key: value for key, value in updates.items() if value is not None})
        side = str(options["side"]).lower()
        fill = str(options["fill"]).lower()
        anchor = str(options["anchor"]).lower()
        if side not in {"top", "bottom", "left", "right"}:
            raise tk.TclError(f'bad side "{side}": must be top, bottom, left, or right')
        if fill not in {"", "none", "x", "y", "both"}:
            raise tk.TclError(f'bad fill style "{fill}": must be none, x, y, or both')
        if anchor not in {"n", "ne", "e", "se", "s", "sw", "w", "nw", "center"}:
            raise tk.TclError(f'bad anchor "{anchor}": must be n, ne, e, se, s, sw, w, nw, or center')
        options.update({
            "side": side,
            "anchor": anchor,
            "fill": "" if fill == "none" else fill,
            "expand": bool(self.tk.getboolean(options["expand"])),
        })
        if options.get("before") is not None and options.get("after") is not None:
            raise tk.TclError("can't specify both -after and -before")
        return self._register_layout("pack", options)

    def _set_anchor(self, anchor: str) -> None:
        self._anchor = anchor

    def _resize_for_place(self, width: int | None, height: int | None) -> None:
        pass

    def _apply_place_layout(self, canvas_width: int | None = None, canvas_height: int | None = None) -> None:
        options = self._layout_options
        if canvas_width is None:
            canvas_width = int(round(self._reverse_widget_scaling(self.canvas.winfo_width())))
            if canvas_width <= 1:
                canvas_width = int(round(self._reverse_widget_scaling(float(self.canvas.cget("width")))))
        if canvas_height is None:
            canvas_height = int(round(self._reverse_widget_scaling(self.canvas.winfo_height())))
            if canvas_height <= 1:
                canvas_height = int(round(self._reverse_widget_scaling(float(self.canvas.cget("height")))))

        x = int(round(float(options.get("x", 0) or 0) + float(options.get("relx", 0) or 0) * canvas_width))
        y = int(round(float(options.get("y", 0) or 0) + float(options.get("rely", 0) or 0) * canvas_height))

        new_width = None
        if "width" in options or "relwidth" in options:
            new_width = max(1, int(round(float(options.get("width", 0) or 0) + float(options.get("relwidth", 0) or 0) * canvas_width)))

        new_height = None
        if "height" in options or "relheight" in options:
            new_height = max(1, int(round(float(options.get("height", 0) or 0) + float(options.get("relheight", 0) or 0) * canvas_height)))

        anchor = options.get("anchor")
        if anchor is not None:
            self._set_anchor(str(anchor))

        self._resize_for_place(new_width, new_height)
        self.move(x, y)

    def place(self, **kwargs: Any) -> None:
        """Match ``CTkBaseClass.place`` while retaining a private layout path.

        CustomTkinter owns desired width/height through construction or
        ``configure`` and deliberately rejects those two options on the public
        ``place`` call.  ``place_configure`` remains the Tk allocation API.
        """
        return self._place_impl(**kwargs)

    def _place_impl(
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
        bordermode: str | None = None,
        in_: Any = None,
        **kwargs: Any,
    ) -> None:
        """Place this canvas item with widget-style absolute and relative options."""
        if isinstance(x, Mapping):
            mapping = dict(x)
            explicit = {
                "y": y, "relx": relx, "rely": rely, "width": width,
                "height": height, "relwidth": relwidth, "relheight": relheight,
                "anchor": anchor, "bordermode": bordermode, "in_": in_,
            }
            mapping.update({key: value for key, value in explicit.items() if value is not None})
            mapping.update(kwargs)
            return self.place(**mapping)
        if "in" in kwargs and in_ is None:
            in_ = kwargs.pop("in")
        if kwargs:
            raise tk.TclError(f"bad option '-{next(iter(kwargs))}'")
        if (
            self._layout_manager != "place"
            and all(
                value is None
                for value in (x, y, relx, rely, width, height, relwidth, relheight, anchor, bordermode, in_)
            )
        ):
            # Tcl's ``place configure <window>`` with no options is a query;
            # it does not remanage a window after ``place_forget``.
            return None
        options = {
            "x": 0,
            "y": 0,
            "relx": 0,
            "rely": 0,
            "anchor": "nw",
            "bordermode": "inside",
        }
        if self._layout_manager == "place":
            options.update(self._layout_options)
        updates = {
            "x": x,
            "y": y,
            "relx": relx,
            "rely": rely,
            "width": width,
            "height": height,
            "relwidth": relwidth,
            "relheight": relheight,
            "anchor": anchor,
            "bordermode": bordermode,
            "in_": in_,
        }
        for key, value in updates.items():
            if value is None:
                continue
            if key in {"width", "height", "relwidth", "relheight"} and value == "":
                options.pop(key, None)
            else:
                options[key] = value
        options["anchor"] = str(options.get("anchor", "nw") or "nw").lower()
        bordermode = str(options.get("bordermode", "inside") or "inside").lower()
        if bordermode not in {"inside", "outside", "ignore"}:
            raise tk.TclError(f'bad bordermode "{bordermode}": must be inside, outside, or ignore')
        if options["anchor"] not in {"n", "ne", "e", "se", "s", "sw", "w", "nw", "center"}:
            raise tk.TclError(f'bad anchor "{options["anchor"]}": must be n, ne, e, se, s, sw, w, nw, or center')
        options["bordermode"] = bordermode
        return self._register_place_layout(options)

    def _register_place_layout(self, options: dict[str, Any]) -> None:
        self._grid_remove_options = None
        self._layout_manager = "place"
        self._layout_options = options

        if self._canvas_host is not None:
            self._canvas_host._attach_child_item(self, "place", self._layout_options)
            self._show_from_geometry()
            return None

        registry = self._registry()
        if self not in registry:
            registry.append(self)
        self._apply_place_layout()
        self._show_from_geometry()
        # The toplevel canvas may still have its pre-geometry size while
        # widgets are constructed. Re-run place at idle so relx/rely and
        # relative dimensions use the realized canvas, matching Tk/CTk.
        self._schedule_canvas_layout()
        return None

    def grid_configure(self, cnf: Mapping[str, Any] | None = None, **kwargs: Any) -> None:
        options = dict(self._layout_options) if self._layout_manager == "grid" else dict(self._grid_remove_options or {})
        options.update(dict(cnf or {}))
        options.update(kwargs)
        if "in" in options and "in_" not in options:
            options["in_"] = options.pop("in")
        return self.grid(**options)

    grid_config = grid_configure

    def pack_configure(self, cnf: Mapping[str, Any] | None = None, **kwargs: Any) -> None:
        options = dict(self._layout_options) if self._layout_manager == "pack" else {}
        options.update(dict(cnf or {}))
        options.update(kwargs)
        if "in" in options and "in_" not in options:
            options["in_"] = options.pop("in")
        return self.pack(**options)

    pack_config = pack_configure

    def place_configure(self, cnf: Mapping[str, Any] | None = None, **kwargs: Any) -> None:
        options = dict(self._layout_options) if self._layout_manager == "place" else {}
        configured = dict(cnf or {})
        configured.update(kwargs)
        physical_keys = getattr(self, "_place_physical_keys", set())
        physical_keys.update(
            key for key in configured if key in {"x", "y", "width", "height"}
        )
        self._place_physical_keys = physical_keys
        options.update(configured)
        if "in" in options and "in_" not in options:
            options["in_"] = options.pop("in")
        return self.place(**options)

    place_config = place_configure

    def coords(self, x: int | None = None, y: int | None = None, **kwargs: Any) -> "Item":
        """Move this canvas item by canvas coordinates, or use widget-style options."""
        if kwargs:
            if x is not None:
                kwargs["x"] = x
            if y is not None:
                kwargs["y"] = y
            return self.place(**kwargs)
        self.move(self._x if x is None else x, self._y if y is None else y)
        self.show()
        return self

    def grid_forget(self) -> None:
        self._grid_remove_options = None
        self._forget_layout()

    def grid_remove(self) -> None:
        if self._layout_manager == "grid":
            self._grid_remove_options = dict(self._layout_options)
        self._forget_layout(preserve_grid=True)

    def pack_forget(self) -> None:
        self._forget_layout()

    def place_forget(self) -> None:
        self._forget_layout()

    def winfo_manager(self) -> str:
        return self._layout_manager

    def _canonical_geometry_info(self, manager: str) -> dict[str, Any]:
        options = dict(self._layout_options)
        scaling = max(float(self._widget_scaling), 1e-9)

        def physical(value: Any) -> Any:
            if isinstance(value, tuple):
                return tuple(round(float(part) * scaling) for part in value)
            if isinstance(value, (int, float)):
                return round(float(value) * scaling)
            return value

        if manager in {"grid", "pack"}:
            for key in ("padx", "pady"):
                if key in options:
                    options[key] = physical(options[key])
        if manager == "pack":
            options["expand"] = int(bool(options.get("expand", False)))
            options["fill"] = str(options.get("fill", "") or "none")
        return options

    def grid_info(self) -> dict[str, Any]:
        if self._layout_manager != "grid":
            return {}
        options = self._canonical_geometry_info("grid")
        options["in"] = options.pop("in_", None) or self.master
        return options

    def pack_info(self) -> dict[str, Any]:
        if self._layout_manager != "pack":
            raise tk.TclError(f'window "{self}" isn\'t packed')
        options = self._canonical_geometry_info("pack")
        options["in"] = options.pop("in_", None) or self.master
        return options

    def place_info(self) -> dict[str, Any]:
        if self._layout_manager != "place":
            return {}
        options = self._canonical_geometry_info("place")
        options.setdefault("width", "")
        options.setdefault("height", "")
        options.setdefault("relwidth", "")
        options.setdefault("relheight", "")
        for key in ("x", "y", "width", "height", "relx", "rely", "relwidth", "relheight"):
            value = options.get(key, "")
            if value != "":
                if key in {"x", "y"} and isinstance(value, (int, float)):
                    value = round(float(value) * self._widget_scaling)
                options[key] = str(value)
        options["in"] = options.pop("in_", None) or self.master
        return options

    def _forget_layout(self, hide: bool = True, preserve_grid: bool = False) -> None:
        if self._layout_manager == "grid" and not preserve_grid:
            self._grid_remove_options = None
        host = self._layout_host
        if host is not None:
            host._forget_child_widget(self, hide=hide)
            self._layout_manager = ""
            self._layout_options = {}
            self._layout_host = None
            return
        registry = self._registry()
        if self in registry:
            registry.remove(self)
        self._layout_manager = ""
        self._layout_options = {}
        self._layout_host = None
        if hide:
            self.hide()
        self._schedule_canvas_layout()

    def _detach_layout(self) -> None:
        host = self._layout_host
        if host is not None:
            host._detach_child_widget(self)
            self._release_canvas_item()
            self._layout_manager = ""
            self._layout_options = {}
            self._layout_host = None
            return
        registry = getattr(self.canvas, "_canvas_ui_widgets", [])
        if self in registry:
            registry.remove(self)
        self._release_canvas_item()
        self._layout_manager = ""
        self._layout_options = {}
        self._layout_host = None

    def _move_bbox(self, left: float, top: float) -> None:
        anchor = self._anchor or "center"
        west_anchors = {"w", "nw", "sw"}
        east_anchors = {"e", "ne", "se"}
        north_anchors = {"n", "ne", "nw"}
        south_anchors = {"s", "se", "sw"}
        x = left if anchor in west_anchors else left + self._width if anchor in east_anchors else left + self._width / 2
        y = top if anchor in north_anchors else top + self._height if anchor in south_anchors else top + self._height / 2
        self.move(int(x), int(y))

    def _relayout_canvas(self) -> None:
        registry = list(getattr(self.canvas, "_canvas_ui_widgets", []))
        width = int(round(self._reverse_widget_scaling(self.canvas.winfo_width())))
        height = int(round(self._reverse_widget_scaling(self.canvas.winfo_height())))
        if width <= 1:
            width = int(round(self._reverse_widget_scaling(float(self.canvas.cget("width")))))
        if height <= 1:
            height = int(round(self._reverse_widget_scaling(float(self.canvas.cget("height")))))

        grid_items = [item for item in registry if item._layout_manager == "grid"]
        if grid_items:
            columns = max(item._layout_options["column"] + item._layout_options["columnspan"] for item in grid_items)
            rows = max(item._layout_options["row"] + item._layout_options["rowspan"] for item in grid_items)
            column_widths = [0] * max(1, columns)
            row_heights = [0] * max(1, rows)
            for item in grid_items:
                options = item._layout_options
                px0, px1 = self._pad(options["padx"])
                py0, py1 = self._pad(options["pady"])
                ipadx = max(0, int(options.get("ipadx", 0) or 0))
                ipady = max(0, int(options.get("ipady", 0) or 0))
                columnspan = max(1, int(options["columnspan"]))
                rowspan = max(1, int(options["rowspan"]))
                requested_width = getattr(item, "_requested_width", item._width) if getattr(item, "_auto_width", False) else item._width
                requested_height = getattr(item, "_requested_height", item._height) if getattr(item, "_auto_height", False) else item._height
                width_share = max(1, (requested_width + ipadx * 2 + px0 + px1 + columnspan - 1) // columnspan)
                height_share = max(1, (requested_height + ipady * 2 + py0 + py1 + rowspan - 1) // rowspan)
                for index in range(options["column"], min(columns, options["column"] + columnspan)):
                    column_widths[index] = max(column_widths[index], width_share)
                for index in range(options["row"], min(rows, options["row"] + rowspan)):
                    row_heights[index] = max(row_heights[index], height_share)

            toplevel = self.canvas.winfo_toplevel()
            column_options: list[dict[str, Any]] = []
            row_options: list[dict[str, Any]] = []
            for index in range(columns):
                try:
                    column_options.append(dict(toplevel.grid_columnconfigure(index)))
                except Exception:
                    column_options.append({})
            for index in range(rows):
                try:
                    row_options.append(dict(toplevel.grid_rowconfigure(index)))
                except Exception:
                    row_options.append({})

            def distribute(sizes: list[int], options: list[dict[str, Any]], available: int) -> None:
                for index, configured in enumerate(options):
                    minimum = max(0, int(configured.get("minsize", 0) or 0))
                    padding = max(0, int(configured.get("pad", 0) or 0))
                    sizes[index] = max(sizes[index], minimum + padding)
                self._distribute_grid_space(sizes, options, available)

            distribute(column_widths, column_options, width)
            distribute(row_heights, row_options, height)
            column_offsets = [0]
            row_offsets = [0]
            for value in column_widths[:-1]:
                column_offsets.append(column_offsets[-1] + value)
            for value in row_heights[:-1]:
                row_offsets.append(row_offsets[-1] + value)

            for item in grid_items:
                options = item._layout_options
                px0, px1 = self._pad(options["padx"])
                py0, py1 = self._pad(options["pady"])
                ipadx = max(0, int(options.get("ipadx", 0) or 0))
                ipady = max(0, int(options.get("ipady", 0) or 0))
                column = options["column"]
                row = options["row"]
                left = column_offsets[column] + px0
                top = row_offsets[row] + py0
                right = column_offsets[column] + sum(column_widths[column:column + options["columnspan"]]) - px1
                bottom = row_offsets[row] + sum(row_heights[row:row + options["rowspan"]]) - py1
                sticky = options["sticky"]
                # Use the propagated request for auto-sized containers.  The
                # current allocation can still be the constructor default
                # when packed/grid children have just established a larger
                # natural size; using it here prevented the outer grid from
                # ever expanding the Frame to those children.
                natural_width = (
                    getattr(item, "_requested_width", item._width)
                    if getattr(item, "_auto_width", False)
                    else item._width
                )
                natural_height = (
                    getattr(item, "_requested_height", item._height)
                    if getattr(item, "_auto_height", False)
                    else item._height
                )
                requested_width = natural_width + ipadx * 2
                requested_height = natural_height + ipady * 2
                # A weighted grid track can become smaller than the widget's
                # natural request when the containing window is constrained.
                # Never center an oversized canvas item across that parcel:
                # doing so moves both edges outside the window and makes the
                # widget appear clipped.  Keep the natural size when it fits,
                # otherwise constrain it to the available grid parcel.
                available_width = max(1, int(right - left))
                available_height = max(1, int(bottom - top))
                target_width = (
                    available_width
                    if "e" in sticky and "w" in sticky
                    else min(requested_width, available_width)
                )
                target_height = (
                    available_height
                    if "n" in sticky and "s" in sticky
                    else min(requested_height, available_height)
                )
                item._resize_for_place(target_width, target_height)
                item_left = left if "w" in sticky else right - item._width if "e" in sticky else left + (right - left - item._width) / 2
                item_top = top if "n" in sticky else bottom - item._height if "s" in sticky else top + (bottom - top - item._height) / 2
                item._move_bbox(item_left, item_top)

        pack_items = [item for item in registry if item._layout_manager == "pack"]
        left_edge, top_edge, right_edge, bottom_edge = 0.0, 0.0, float(width), float(height)
        natural_sizes: dict[Item, tuple[int, int]] = {}
        vertical_request = horizontal_request = 0
        vertical_expanders = horizontal_expanders = 0
        for item in pack_items:
            options = item._layout_options
            px0, px1 = self._pad(options.get("padx", 0))
            py0, py1 = self._pad(options.get("pady", 0))
            ipadx = max(0, int(options.get("ipadx", 0) or 0))
            ipady = max(0, int(options.get("ipady", 0) or 0))
            requested_width = getattr(item, "_requested_width", item._width) if getattr(item, "_auto_width", False) else item._width
            requested_height = getattr(item, "_requested_height", item._height) if getattr(item, "_auto_height", False) else item._height
            natural_sizes[item] = (requested_width + ipadx * 2, requested_height + ipady * 2)
            if options["side"] in {"top", "bottom"}:
                vertical_request += natural_sizes[item][1] + py0 + py1
                vertical_expanders += int(bool(options.get("expand", False)))
            else:
                horizontal_request += natural_sizes[item][0] + px0 + px1
                horizontal_expanders += int(bool(options.get("expand", False)))
        vertical_extra = max(0, height - vertical_request)
        horizontal_extra = max(0, width - horizontal_request)
        vertical_index = horizontal_index = 0
        for item in pack_items:
            options = item._layout_options
            px0, px1 = self._pad(options["padx"])
            py0, py1 = self._pad(options["pady"])
            side = options["side"]
            cross_anchor = options["anchor"]
            fill = options.get("fill", "")
            expand = bool(options.get("expand", False))
            fill_x = fill in ("x", "both")
            fill_y = fill in ("y", "both")
            west_anchors = {"w", "nw", "sw"}
            east_anchors = {"e", "ne", "se"}
            north_anchors = {"n", "ne", "nw"}
            south_anchors = {"s", "se", "sw"}
            natural_width, natural_height = natural_sizes[item]
            if side in ("left", "right"):
                extra = 0
                if expand and horizontal_expanders:
                    quotient, remainder = divmod(horizontal_extra, horizontal_expanders)
                    extra = quotient + int(horizontal_index < remainder)
                    horizontal_index += 1
                remaining_width = max(1.0, right_edge - left_edge)
                parcel_width = min(natural_width + px0 + px1 + extra, remaining_width)
                parcel_left = left_edge if side == "left" else right_edge - parcel_width
                available_width = max(1, int(parcel_width - px0 - px1))
                available_height = max(1, int(bottom_edge - top_edge - py0 - py1))
                target_width = available_width if fill_x else natural_width
                target_height = available_height if fill_y else natural_height
                inner_left = parcel_left + px0
                inner_top = top_edge + py0
                if fill_x or cross_anchor in west_anchors:
                    item_left = inner_left
                elif cross_anchor in east_anchors:
                    item_left = inner_left + available_width - target_width
                else:
                    item_left = inner_left + (available_width - target_width) / 2
                if fill_y or cross_anchor in north_anchors:
                    item_top = inner_top
                elif cross_anchor in south_anchors:
                    item_top = inner_top + available_height - target_height
                else:
                    item_top = inner_top + (available_height - target_height) / 2
                if side == "left":
                    left_edge += parcel_width
                else:
                    right_edge -= parcel_width
            else:
                extra = 0
                if expand and vertical_expanders:
                    quotient, remainder = divmod(vertical_extra, vertical_expanders)
                    extra = quotient + int(vertical_index < remainder)
                    vertical_index += 1
                remaining_height = max(1.0, bottom_edge - top_edge)
                parcel_height = min(natural_height + py0 + py1 + extra, remaining_height)
                parcel_top = top_edge if side == "top" else bottom_edge - parcel_height
                available_width = max(1, int(right_edge - left_edge - px0 - px1))
                available_height = max(1, int(parcel_height - py0 - py1))
                target_width = available_width if fill_x else natural_width
                target_height = available_height if fill_y else natural_height
                inner_left = left_edge + px0
                inner_top = parcel_top + py0
                if fill_x or cross_anchor in west_anchors:
                    item_left = inner_left
                elif cross_anchor in east_anchors:
                    item_left = inner_left + available_width - target_width
                else:
                    item_left = inner_left + (available_width - target_width) / 2
                if fill_y or cross_anchor in north_anchors:
                    item_top = inner_top
                elif cross_anchor in south_anchors:
                    item_top = inner_top + available_height - target_height
                else:
                    item_top = inner_top + (available_height - target_height) / 2
                if side == "top":
                    top_edge += parcel_height
                else:
                    bottom_edge -= parcel_height
            item._resize_for_place(target_width, target_height)
            item._move_bbox(item_left, item_top)

        for item in [item for item in registry if item._layout_manager == "place"]:
            item._apply_place_layout(width, height)
