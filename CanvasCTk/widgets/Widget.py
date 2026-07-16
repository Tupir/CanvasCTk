from ._shared import *

class Widget(ElementBase):
    def __init__(self, master: Any, **kwargs: Any) -> None:
        ElementBase.__init__(self, **kwargs)
        self.master = master
        self._logical_master = master
        self._canvas_host = master if hasattr(master, "_attach_child_widget") else None
        self._tk_master = master._widget_parent() if self._canvas_host is not None else master
        self._grid_remove_options: dict[str, Any] | None = None
        self.is_hidden = True

    def get_resource_path(self, resource_path: str | Path = "") -> Path:
        if self.resource_override is not None:
            return Path(self.resource_override) / resource_path
        master = getattr(self, "_logical_master", self.master)
        if hasattr(master, "get_resource_path"):
            return Path(master.get_resource_path(resource_path))
        return Path(resource_path)

    def grid(self, **kwargs: Any) -> Any:
        if self._canvas_host is not None:
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
            if self.manager == "grid":
                options.update(self._last_geometry.get("grid", {}))
            elif self._grid_remove_options is not None:
                options.update(self._grid_remove_options)
            options.update(kwargs)
            self.manager = "grid"
            self._last_geometry["grid"] = options
            self._grid_remove_options = None
            self.is_hidden = False
            self._canvas_host._attach_child_widget(self, "grid", options)
            self._canvas_host._show_child_widget(self)
            return None
        self.is_hidden = False
        return super().grid(**kwargs)

    def place(self, **kwargs: Any) -> Any:
        if self._canvas_host is not None:
            options = {"x": 0, "y": 0, "relx": 0, "rely": 0, "anchor": "nw", "bordermode": "inside"}
            if self.manager == "place":
                options.update(self._last_geometry.get("place", {}))
            options.update(kwargs)
            self.manager = "place"
            self._last_geometry["place"] = options
            self._grid_remove_options = None
            self.is_hidden = False
            self._canvas_host._attach_child_widget(self, "place", options)
            self._canvas_host._show_child_widget(self)
            return None
        self.is_hidden = False
        return super().place(**kwargs)

    def pack(self, **kwargs: Any) -> Any:
        if self._canvas_host is not None:
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
            if self.manager == "pack":
                options.update(self._last_geometry.get("pack", {}))
            options.update(kwargs)
            self.manager = "pack"
            self._last_geometry["pack"] = options
            self._grid_remove_options = None
            self.is_hidden = False
            self._canvas_host._attach_child_widget(self, "pack", options)
            self._canvas_host._show_child_widget(self)
            return None
        self.is_hidden = False
        return super().pack(**kwargs)

    def grid_forget(self) -> None:
        if self._canvas_host is not None:
            self._grid_remove_options = None
            self.manager = None
            self._canvas_host._forget_child_widget(self)
            return
        super().grid_forget()

    def grid_remove(self) -> None:
        if self._canvas_host is not None:
            if self.manager == "grid":
                self._grid_remove_options = dict(self._last_geometry.get("grid", {}))
            self.manager = None
            self._canvas_host._forget_child_widget(self)
            return
        super().grid_remove()

    def pack_forget(self) -> None:
        if self._canvas_host is not None:
            self.manager = None
            self._canvas_host._forget_child_widget(self)
            return
        super().pack_forget()

    def place_forget(self) -> None:
        if self._canvas_host is not None:
            self.manager = None
            self._canvas_host._forget_child_widget(self)
            return
        super().place_forget()

    def grid_configure(self, cnf: Mapping[str, Any] | None = None, **kwargs: Any) -> Any:
        options = dict(cnf or {})
        options.update(kwargs)
        if self._canvas_host is not None:
            merged = (
                dict(self._last_geometry.get("grid", {}))
                if self.manager == "grid"
                else dict(self._grid_remove_options or {})
            )
            merged.update(options)
            return self.grid(**merged)
        return super().grid_configure(**options)

    grid_config = grid_configure

    def pack_configure(self, cnf: Mapping[str, Any] | None = None, **kwargs: Any) -> Any:
        options = dict(cnf or {})
        options.update(kwargs)
        if self._canvas_host is not None:
            merged = dict(self._last_geometry.get("pack", {})) if self.manager == "pack" else {}
            merged.update(options)
            return self.pack(**merged)
        return super().pack_configure(**options)

    pack_config = pack_configure

    def place_configure(self, cnf: Mapping[str, Any] | None = None, **kwargs: Any) -> Any:
        options = dict(cnf or {})
        options.update(kwargs)
        if self._canvas_host is not None:
            merged = dict(self._last_geometry.get("place", {})) if self.manager == "place" else {}
            merged.update(options)
            return self.place(**merged)
        return super().place_configure(**options)

    place_config = place_configure

    def grid_info(self) -> dict[str, Any]:
        if self._canvas_host is not None:
            if self.manager != "grid":
                return {}
            options = dict(self._last_geometry.get("grid", {}))
            options.setdefault("in", self._logical_master)
            return options
        return super().grid_info()

    def pack_info(self) -> dict[str, Any]:
        if self._canvas_host is not None:
            if self.manager != "pack":
                return {}
            options = dict(self._last_geometry.get("pack", {}))
            options.setdefault("in", self._logical_master)
            return options
        return super().pack_info()

    def place_info(self) -> dict[str, Any]:
        if self._canvas_host is not None:
            if self.manager != "place":
                return {}
            options = dict(self._last_geometry.get("place", {}))
            options.setdefault("width", "")
            options.setdefault("height", "")
            options.setdefault("relwidth", "")
            options.setdefault("relheight", "")
            options.setdefault("in", self._logical_master)
            return options
        return super().place_info()

    def winfo_manager(self) -> str:
        if self._canvas_host is not None:
            return self.manager or ""
        return super().winfo_manager()

    def _hide(self) -> None:
        if self._canvas_host is not None:
            self._canvas_host._hide_child_widget(self)
            return
        super()._hide()

    def _show(self) -> None:
        if self._canvas_host is not None:
            self._canvas_host._show_child_widget(self)
            return
        super()._show()

    def destroy(self) -> None:
        if self._canvas_host is not None:
            self._canvas_host._detach_child_widget(self)
        self._cleanup_canvas_element()
        super().destroy()


