from __future__ import annotations

import sys
import tkinter as tk
from typing import Any, Callable

import customtkinter as ctk

from ..containers import ScrollableFrame
from ..widgets.Button import Button
from ..widgets.OptionMenu import OptionMenu
from ..windows import Toplevel


class _DropdownToplevel(Toplevel):
    """Borderless internal popup without CTk title-bar redraw callbacks."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._deactivate_windows_window_header_manipulation = True
        super().__init__(*args, **kwargs)
        self.withdraw()


class _ScrollableMenuAdapter:
    """Present the dropdown interface expected by OptionMenu."""

    def __init__(self, owner: "ScrollableDropdown") -> None:
        self._owner = owner

    def open(self, x: int, y: int) -> None:
        self._owner._open_scrollable_dropdown(x, y)

    def configure(self, **kwargs: Any) -> None:
        self._owner._refresh_open_dropdown(**kwargs)

    config = configure

    def destroy(self) -> None:
        self._owner._close_dropdown()


class ScrollableDropdown(OptionMenu):
    """A CanvasCTk OptionMenu with a scrollable CanvasCTk dropdown."""

    _active_dropdown: "ScrollableDropdown | None" = None

    def __init__(
        self,
        master: Any,
        width: int = 140,
        height: int = 28,
        corner_radius: int | None = None,
        bg_color: Any = "transparent",
        fg_color: Any = None,
        button_color: Any = None,
        button_hover_color: Any = None,
        text_color: Any = None,
        text_color_disabled: Any = None,
        dropdown_fg_color: Any = None,
        dropdown_hover_color: Any = None,
        dropdown_text_color: Any = None,
        font: tuple | ctk.CTkFont | None = None,
        dropdown_font: tuple | ctk.CTkFont | None = None,
        values: Any = None,
        variable: tk.Variable | None = None,
        state: str = tk.NORMAL,
        hover: bool = True,
        command: Callable[[Any], Any] | None = None,
        dynamic_resizing: bool = True,
        anchor: str = "w",
        *,
        dropdown_max_height: int = 400,
        **kwargs: Any,
    ) -> None:
        self._dropdown_max_height = self._validate_dropdown_max_height(dropdown_max_height)
        self._top_level: Toplevel | None = None
        self._outside_bindings: list[tuple[Any, str, str]] = []
        self._open_after_id: str | None = None
        self._focus_force_after_id: str | None = None
        self._focus_check_after_id: str | None = None
        super().__init__(
            master,
            width=width,
            height=height,
            corner_radius=corner_radius,
            bg_color=bg_color,
            fg_color=fg_color,
            button_color=button_color,
            button_hover_color=button_hover_color,
            text_color=text_color,
            text_color_disabled=text_color_disabled,
            dropdown_fg_color=dropdown_fg_color,
            dropdown_hover_color=dropdown_hover_color,
            dropdown_text_color=dropdown_text_color,
            font=font,
            dropdown_font=dropdown_font,
            values=values,
            variable=variable,
            state=state,
            hover=hover,
            command=command,
            dynamic_resizing=dynamic_resizing,
            anchor=anchor,
            **kwargs,
        )

    def _create_dropdown_menu(self) -> _ScrollableMenuAdapter:
        return _ScrollableMenuAdapter(self)

    @staticmethod
    def _validate_dropdown_max_height(value: Any) -> int:
        try:
            height = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError("dropdown_max_height must be a positive integer") from error
        if height <= 0:
            raise ValueError("dropdown_max_height must be greater than 0")
        return height

    @staticmethod
    def _point_inside(widget: Any, x_root: int, y_root: int) -> bool:
        try:
            left = widget.winfo_rootx()
            top = widget.winfo_rooty()
            return (
                left <= x_root < left + widget.winfo_width()
                and top <= y_root < top + widget.winfo_height()
            )
        except (AttributeError, tk.TclError):
            return False

    def _cancel_after(self, attribute: str) -> None:
        after_id = getattr(self, attribute)
        if after_id is None:
            return
        try:
            self.after_cancel(after_id)
        except tk.TclError:
            pass
        setattr(self, attribute, None)

    def _focus_dropdown(self) -> None:
        self._focus_force_after_id = None
        try:
            if self._top_level is not None and self._top_level.winfo_exists():
                self._top_level.focus_set()
        except tk.TclError:
            pass

    def _clicked(self, _event: Any = None) -> None:
        if self._state == tk.DISABLED or not self._values:
            return
        if self._open_after_id is not None:
            return
        self._open_after_id = self.after_idle(self._open_dropdown_after_click)

    def _open_dropdown_after_click(self) -> None:
        self._open_after_id = None
        if self._destroyed or self._state == tk.DISABLED or not self._values:
            return
        self._open_dropdown_menu()

    def _remove_dropdown_bindings(self) -> None:
        for widget, sequence, bind_id in self._outside_bindings:
            try:
                widget.unbind(sequence, bind_id)
            except (AttributeError, tk.TclError):
                pass
        self._outside_bindings.clear()

    def _install_dropdown_bindings(self) -> None:
        self._remove_dropdown_bindings()
        if self._top_level is None or not self._top_level.winfo_exists():
            return
        owner = self.winfo_toplevel()
        for widget, sequence, callback in (
            (owner, "<ButtonPress-1>", self._on_window_click),
            (self._top_level, "<ButtonPress-1>", self._on_window_click),
            (self._top_level, "<FocusOut>", self._on_focus_out),
            (self._top_level, "<Destroy>", self._on_popup_destroy),
        ):
            bind_id = widget.bind(sequence, callback, add="+")
            if bind_id:
                self._outside_bindings.append((widget, sequence, bind_id))

    def _on_window_click(self, event: Any = None) -> None:
        if self._top_level is None or not self._top_level.winfo_exists():
            return
        x_root = getattr(event, "x_root", self.winfo_pointerx())
        y_root = getattr(event, "y_root", self.winfo_pointery())
        if self._point_inside(self, x_root, y_root):
            return
        if self._point_inside(self._top_level, x_root, y_root):
            return
        self._close_dropdown()

    def _on_popup_destroy(self, event: Any = None) -> None:
        if self._top_level is not None and getattr(event, "widget", None) is self._top_level:
            self._remove_dropdown_bindings()
            self._top_level = None
            if ScrollableDropdown._active_dropdown is self:
                ScrollableDropdown._active_dropdown = None

    def _on_focus_out(self, event: Any = None) -> None:
        if self._top_level is None or not self._top_level.winfo_exists():
            return
        self._cancel_after("_focus_check_after_id")
        self._focus_check_after_id = self.after_idle(self._close_if_focus_outside)

    def _close_if_focus_outside(self) -> None:
        self._focus_check_after_id = None
        if self._top_level is None or not self._top_level.winfo_exists():
            return
        try:
            focused = self._top_level.focus_get()
            if focused is not None and focused.winfo_toplevel() is self._top_level:
                return
        except (AttributeError, tk.TclError):
            pass
        self._close_dropdown()

    @staticmethod
    def _destroy_popup(popup: Any) -> None:
        try:
            if popup.winfo_exists():
                popup.destroy()
        except tk.TclError:
            pass

    def _close_dropdown(self, restore_focus: bool = False) -> None:
        self._cancel_after("_focus_force_after_id")
        self._cancel_after("_focus_check_after_id")
        popup = self._top_level
        self._top_level = None
        if ScrollableDropdown._active_dropdown is self:
            ScrollableDropdown._active_dropdown = None
        self._remove_dropdown_bindings()
        if popup is not None:
            try:
                if popup.winfo_exists():
                    popup.destroy()
            except tk.TclError:
                pass
        if restore_focus:
            try:
                self.canvas.focus_set()
            except tk.TclError:
                pass

    def _open_scrollable_dropdown(self, x: int, y: int) -> None:
        active_dropdown = ScrollableDropdown._active_dropdown
        if active_dropdown is not None and active_dropdown is not self:
            active_dropdown._close_dropdown()
        if self._top_level is not None:
            self._close_dropdown()
        ScrollableDropdown._active_dropdown = self
        dropdown_width = max(self.winfo_width(), 100)
        self._dropdown_width = dropdown_width
        owner = self.winfo_toplevel()
        popup_backing_color = self._bg_color
        self._top_level = _DropdownToplevel(owner, fg_color=popup_backing_color)
        self._top_level.geometry(f"{dropdown_width}x1+{x}+{y}")
        self._top_level.wm_overrideredirect(True)
        self._top_level.wm_attributes("-topmost", True)
        self._top_level.wm_transient(owner)
        self._top_level.frame = ScrollableFrame(
            self._top_level,
            bg_color=popup_backing_color,
            fg_color=self._dropdown_fg_color,
            corner_radius=self._corner_radius,
            border_width=0,
        )
        self._top_level.frame.pack(fill="both", expand=True)
        self._build_values()
        self._top_level.geometry(f"+{int(x)}+{int(y)}")
        self._top_level.deiconify()
        self._top_level.update_idletasks()
        self._apply_compositor_rounding()
        self._top_level.lift()
        self._install_dropdown_bindings()
        self._cancel_after("_focus_force_after_id")
        self._focus_force_after_id = self.after(10, self._focus_dropdown)

    def _apply_compositor_rounding(self) -> None:
        popup = self._top_level
        if popup is None or not popup.winfo_exists() or not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = popup.winfo_id()
            get_parent = ctypes.windll.user32.GetParent
            get_parent.argtypes = (wintypes.HWND,)
            get_parent.restype = wintypes.HWND
            wrapper = get_parent(hwnd) or hwnd
            preference = ctypes.c_int(3 if self._corner_radius > 0 else 1)
            set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
            set_attribute.argtypes = (
                wintypes.HWND,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.DWORD,
            )
            set_attribute.restype = wintypes.LONG
            set_attribute(
                wrapper,
                33,
                ctypes.byref(preference),
                ctypes.sizeof(preference),
            )
        except (AttributeError, OSError, tk.TclError):
            pass

    def _refresh_open_dropdown(self, **kwargs: Any) -> None:
        if self._top_level is None or not self._top_level.winfo_exists():
            return
        if "fg_color" in kwargs:
            self._top_level.frame.configure(fg_color=kwargs["fg_color"])
        self._build_values()

    def _build_values(self) -> None:
        if self._top_level is None or not self._top_level.winfo_exists():
            return
        for button in self._top_level.frame.winfo_children():
            button.destroy()
        logical_popup_width = max(
            1,
            int(round(self._reverse_widget_scaling(self._dropdown_width))),
        )
        button_width = max(
            1,
            logical_popup_width
            - self._top_level.frame._border_spacing()
            - self._top_level.frame._scrollbar_thickness
            - 1,
        )
        self._top_level.frame.grid_columnconfigure(1, weight=1)
        for row, value in enumerate(self._values):
            button = Button(
                self._top_level.frame,
                width=button_width,
                text=self._display(value),
                text_color=self._dropdown_text_color,
                hover_color=self._dropdown_hover_color,
                fg_color="transparent",
                anchor="w",
                font=self._dropdown_font,
                command=lambda selected=value: self._selected(selected),
            )
            button.configure(wraplength=max(1, button_width - 12))
            button.grid(row=row, column=1, sticky="ew")
        self._resize_dropdown()

    def _resize_dropdown(self) -> None:
        if self._top_level is None or not self._top_level.winfo_exists():
            return
        self._top_level.frame.update_idletasks()
        gap_to_bottom = self.winfo_screenheight() - (
            self.winfo_rooty() + self.winfo_height()
        ) - 20
        spacing = self._top_level.frame._border_spacing()
        requested_height = (
            self._top_level.frame.winfo_reqheight()
            + int(round(self._apply_widget_scaling(spacing * 2)))
        )
        scaled_max_height = max(
            1,
            int(round(self._apply_widget_scaling(self._dropdown_max_height))),
        )
        requested_height = min(
            requested_height,
            max(1, gap_to_bottom),
            scaled_max_height,
        )
        self._top_level.geometry(f"{self._dropdown_width}x{requested_height}")
        self._top_level.update_idletasks()

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        resize_dropdown = False
        if "dropdown_max_height" in kwargs:
            self._dropdown_max_height = self._validate_dropdown_max_height(
                kwargs.pop("dropdown_max_height")
            )
            resize_dropdown = True
        super().configure(require_redraw=require_redraw, **kwargs)
        if resize_dropdown:
            self._resize_dropdown()

    config = configure

    def cget(self, attribute_name: str) -> Any:
        if attribute_name == "dropdown_max_height":
            return self._dropdown_max_height
        return super().cget(attribute_name)

    def _selected(self, value: Any) -> None:
        self._close_dropdown(restore_focus=True)
        self._dropdown_callback(value)

    def destroy(self) -> None:
        self._cancel_after("_open_after_id")
        super().destroy()


__all__ = ["ScrollableDropdown"]
