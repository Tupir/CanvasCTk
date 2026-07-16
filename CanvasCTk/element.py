from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from customtkinter import ThemeManager

from .tooltip import ToolTip


class Element:
    """Shared ownership, visibility, theming, resources, and tooltip behavior."""

    def __init__(self, **_: Any) -> None:
        self._id: str | None = None
        self.elements: dict[str, Element] = {}
        self._element_identity_keys: dict[int, str] = {}
        self._element_index = 0
        self.tooltip: ToolTip | None = None
        self.enabled = True
        self.is_hidden = False
        self.resource_override: Path | None = None
        self._traces: list[tuple[Any, str]] = []
        self._theme_defaults: dict[str, tuple[str, str | tuple[str, ...]]] = {}
        self._destroyed = False
        self._lifecycle_bindings: dict[str, dict[str, Callable[..., Any]]] = {}
        self._lifecycle_binding_index = 0

    @staticmethod
    def _is_lifecycle_event(sequence: str | None) -> bool:
        return sequence == "<Destroy>"

    def _bind_lifecycle_event(
        self,
        sequence: str,
        callback: Callable[..., Any] | None,
        add: str | bool | None = None,
    ) -> str | None:
        callbacks = self._lifecycle_bindings.setdefault(sequence, {})
        if callback is None:
            return None
        if add not in ("+", True):
            callbacks.clear()
        self._lifecycle_binding_index += 1
        funcid = f"canvasctk_lifecycle_{id(self)}_{self._lifecycle_binding_index}"
        callbacks[funcid] = callback
        return funcid

    def _unbind_lifecycle_event(self, sequence: str, funcid: str | None = None) -> None:
        callbacks = self._lifecycle_bindings.get(sequence)
        if callbacks is None:
            return
        if funcid is None:
            callbacks.clear()
        else:
            callbacks.pop(funcid, None)

    def _emit_destroy_event(self) -> None:
        callbacks = tuple(self._lifecycle_bindings.get("<Destroy>", {}).values())
        event = SimpleNamespace(widget=self)
        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                pass
        self._lifecycle_bindings.clear()

    def put(self, element: "Element") -> "Element":
        identity = id(element)
        existing_key = self._element_identity_keys.get(identity)
        if existing_key is not None and self.elements.get(existing_key) is element:
            return element
        self._element_identity_keys.pop(identity, None)
        element._id = f"{element.__class__.__name__}_{self._element_index}"
        self._element_index += 1
        self.elements[element._id] = element
        self._element_identity_keys[identity] = element._id
        return element

    def grab(self, cls: str | type) -> "Element | None":
        for element in self.elements.values():
            if (isinstance(cls, str) and element.__class__.__name__ == cls) or (
                not isinstance(cls, str) and isinstance(element, cls)
            ):
                return element
        return None

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        try:
            self.configure(state="normal" if enabled else "disabled")
        except Exception:
            pass

    def trace_write(self, variable: Any, callback: Callable[..., Any]) -> str:
        def dispatch(*_: Any) -> None:
            value = variable.get()
            try:
                callback(variable, value)
            except TypeError:
                callback(value)

        trace_id = variable.trace_add("write", dispatch)
        self._traces.append((variable, trace_id))
        dispatch()
        return trace_id

    def untrace_write(self) -> None:
        for variable, trace_id in self._traces:
            try:
                variable.trace_remove("write", trace_id)
            except Exception:
                pass
        self._traces.clear()

    def hide(self, hide: bool = True) -> None:
        if not hide:
            self.show()
            return
        self.is_hidden = True
        for element in self.elements.values():
            element.hide()
        self._hide()

    def show(self, show: bool = True) -> None:
        if not show or not self.enabled:
            self.hide()
            return
        self.is_hidden = False
        for element in self.elements.values():
            element.show()
        self._show()

    def _hide(self) -> None:
        raise NotImplementedError

    def _show(self) -> None:
        raise NotImplementedError

    def set_tooltip(self, message: str | Callable[[], str], **kwargs: Any) -> ToolTip:
        if self.tooltip is not None:
            self.tooltip.destroy()
        self.tooltip = ToolTip(self, message, **kwargs)
        return self.tooltip

    def get_resource_path(self, resource_path: str | Path = "") -> Path:
        if self.resource_override is not None:
            return Path(self.resource_override) / resource_path
        master = getattr(self, "master", None)
        if master is not None and hasattr(master, "get_resource_path"):
            return Path(master.get_resource_path(resource_path))
        return Path(resource_path)

    def _track_theme_defaults(self, theme_key: str, **options: bool | str | tuple[str, ...]) -> None:
        """Remember constructor options that came from CustomTkinter's theme.

        A string maps a CanvasCTk option to a differently named theme option.
        A tuple lists theme options in fallback order.
        """
        for option, theme_option in options.items():
            if theme_option is True:
                self._theme_defaults[option] = (theme_key, option)
            elif isinstance(theme_option, str):
                self._theme_defaults[option] = (theme_key, theme_option)
            elif isinstance(theme_option, tuple) and theme_option:
                self._theme_defaults[option] = (theme_key, theme_option)

    def get_color(self, key: str, default: Any = ("white", "black")) -> Any:
        for theme_key, _ in self._theme_defaults.values():
            if key in ThemeManager.theme.get(theme_key, {}):
                return ThemeManager.theme[theme_key][key]
        return ThemeManager.theme.get(self.__class__.__qualname__, {}).get(key, default)

    def _apply_theme(self, recursive: bool = False) -> None:
        updates: dict[str, Any] = {}
        for option, (theme_key, theme_option) in tuple(self._theme_defaults.items()):
            theme = ThemeManager.theme.get(theme_key, {})
            candidates = (theme_option,) if isinstance(theme_option, str) else theme_option
            value = next((theme[candidate] for candidate in candidates if candidate in theme), None)
            if value is None:
                continue
            try:
                current = self.cget(option)
            except Exception:
                current = object()
            if not self._theme_values_equal(current, value):
                updates[option] = value
        if updates:
            try:
                self.configure(**updates)
            except Exception:
                # Preserve the old best-effort behavior for third-party
                # Element subclasses which only accept one option at a time.
                for option, value in updates.items():
                    try:
                        self.configure(**{option: value})
                    except Exception:
                        pass
        if recursive:
            for element in self.elements.values():
                element._apply_theme(True)

    @staticmethod
    def _theme_values_equal(current: Any, requested: Any) -> bool:
        if isinstance(current, (tuple, list)) and isinstance(requested, (tuple, list)):
            return tuple(current) == tuple(requested)
        try:
            return bool(current == requested)
        except Exception:
            return False

    def _cleanup_canvas_element(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        self._emit_destroy_event()
        if self.tooltip is not None:
            self.tooltip.destroy()
            self.tooltip = None
        self.untrace_write()
        for element in tuple(self.elements.values()):
            try:
                element.destroy()
            except Exception:
                pass
        self.elements.clear()
        self._element_identity_keys.clear()


class ElementBase(Element):
    def __init__(self, **kwargs: Any) -> None:
        Element.__init__(self, **kwargs)
        self.manager: str | None = None
        self._last_geometry: dict[str, dict[str, Any]] = {}

    def grid(self, **kwargs: Any) -> Any:
        self.manager = "grid"
        if kwargs:
            self._last_geometry["grid"] = kwargs
        result = super().grid(**kwargs)
        if self.is_hidden:
            super().grid_remove()
        return result

    def place(self, **kwargs: Any) -> Any:
        self.manager = "place"
        if kwargs:
            self._last_geometry["place"] = kwargs
        return super().place(**kwargs)

    def pack(self, **kwargs: Any) -> Any:
        self.manager = "pack"
        if kwargs:
            self._last_geometry["pack"] = kwargs
        return super().pack(**kwargs)

    def _hide(self) -> None:
        manager = self.manager or self.winfo_manager()
        if manager == "grid":
            super().grid_remove()
        elif manager == "place":
            super().place_forget()
        elif manager == "pack":
            super().pack_forget()

    def _show(self) -> None:
        manager = self.manager
        if manager == "grid":
            super().grid(**self._last_geometry.get("grid", {}))
        elif manager == "place":
            super().place(**self._last_geometry.get("place", {}))
        elif manager == "pack":
            super().pack(**self._last_geometry.get("pack", {}))
