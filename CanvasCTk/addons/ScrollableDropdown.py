from __future__ import annotations

import ast
import sys
import tkinter as tk
from collections.abc import Iterable, Mapping
from typing import Any, Callable

import customtkinter as ctk

from ..containers import ScrollableFrame
from ..widgets.Button import Button
from ..widgets.Entry import Entry
from ..widgets.OptionMenu import OptionMenu
from ..windows import Toplevel


class _DropdownToplevel(Toplevel):
    """Borderless internal popup without CTk title-bar redraw callbacks."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._deactivate_windows_window_header_manipulation = True
        kwargs.setdefault("no_titlebar", True)
        super().__init__(*args, **kwargs)
        self.withdraw()

    def _canvasctk_show_on_creation(self) -> None:
        return


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
        show_selection: bool = True,
        multiple_choice: bool = False,
        search_bar: bool = False,
        search_placeholder_text: str = "Search...",
        **kwargs: Any,
    ) -> None:
        self._dropdown_max_height = self._validate_dropdown_max_height(dropdown_max_height)
        self._show_selection = bool(show_selection)
        self._multiple_choice = bool(multiple_choice)
        self._search_bar = bool(search_bar)
        self._search_placeholder_text = str(search_placeholder_text)
        self._selected_values: list[Any] = []
        self._top_level: Toplevel | None = None
        self._outside_bindings: list[tuple[Any, str, str]] = []
        self._open_after_id: str | None = None
        self._focus_force_after_id: str | None = None
        self._focus_check_after_id: str | None = None
        self._scroll_after_id: str | None = None
        self._selected_dropdown_button: Button | None = None
        self._dropdown_value_buttons: list[tuple[Any, Button]] = []
        self._search_entry: Entry | None = None
        self._search_variable: tk.StringVar | None = None
        self._search_trace_id: str | None = None
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
        if self._multiple_choice:
            initial_values = (
                self._variable.get()
                if self._variable is not None
                else []
            )
            self._set_multiple_values(initial_values, update_variable=False)

    def _create_dropdown_menu(self) -> _ScrollableMenuAdapter:
        return _ScrollableMenuAdapter(self)

    def _draw(self, *args: Any, no_color_updates: bool = False) -> None:
        if self._multiple_choice and hasattr(self, "_dynamic_resizing"):
            dynamic_resizing = self._dynamic_resizing
            self._dynamic_resizing = False
            try:
                super()._draw(*args, no_color_updates=no_color_updates)
            finally:
                self._dynamic_resizing = dynamic_resizing
            return
        super()._draw(*args, no_color_updates=no_color_updates)

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

    def _brighten_dropdown_color(self, color: Any, amount: float = 0.18) -> Any:
        if isinstance(color, (tuple, list)):
            return tuple(
                self._brighten_dropdown_color(part, amount)
                for part in color
            )
        try:
            red, green, blue = self.canvas.winfo_rgb(color)
        except (tk.TclError, TypeError):
            return color
        channels = (
            round(channel / 257 + (255 - channel / 257) * amount)
            for channel in (red, green, blue)
        )
        return "#{:02x}{:02x}{:02x}".format(*channels)

    def _value_matches_current(self, value: Any) -> bool:
        if self._multiple_choice:
            return any(
                self._choices_equal(value, selected)
                for selected in self._selected_values
            )
        current = self.get()
        try:
            if bool(value == current):
                return True
        except (TypeError, ValueError):
            if value is current:
                return True
        return self._display(value) == str(current)

    @staticmethod
    def _choices_equal(left: Any, right: Any) -> bool:
        try:
            return bool(left == right)
        except (TypeError, ValueError):
            return left is right

    def _resolve_choice(self, value: Any) -> Any:
        for choice in self._values:
            if self._choices_equal(choice, value):
                return choice
        if isinstance(value, str) and value in self._reverse_map:
            return self._reverse_map[value]
        if isinstance(value, str):
            for choice in self._values:
                if str(choice) == value:
                    return choice
        return value

    def _normalize_multiple_values(self, values: Any) -> list[Any]:
        if values is None or (isinstance(values, str) and values == ""):
            return []
        resolved_single = self._resolve_choice(values)
        if any(
            self._choices_equal(resolved_single, choice)
            for choice in self._values
        ):
            candidates = [resolved_single]
        elif isinstance(values, str):
            parsed_values: Any = None
            if values.lstrip().startswith(("[", "(")):
                try:
                    parsed_values = ast.literal_eval(values)
                except (SyntaxError, ValueError):
                    pass
            if isinstance(parsed_values, (list, tuple, set)):
                candidates = list(parsed_values)
            else:
                try:
                    candidates = list(self.tk.splitlist(values))
                except tk.TclError:
                    candidates = [values]
        elif isinstance(values, Iterable) and not isinstance(values, Mapping):
            candidates = list(values)
        else:
            candidates = [values]

        normalized: list[Any] = []
        for candidate in candidates:
            choice = self._resolve_choice(candidate)
            if not any(
                self._choices_equal(choice, selected)
                for selected in normalized
            ):
                normalized.append(choice)
        return normalized

    def _set_multiple_values(
        self,
        values: Any,
        *,
        update_variable: bool = True,
    ) -> None:
        self._selected_values = self._normalize_multiple_values(values)
        self._current_value = ", ".join(
            self._display(value) for value in self._selected_values
        )
        self._draw()
        if update_variable and self._variable is not None:
            self._variable_callback_blocked = True
            try:
                tcl_values = self.tk.call(
                    "list",
                    *(str(value) for value in self._selected_values),
                )
                serialized_values = str(
                    self.tk.call("format", "%s", tcl_values)
                )
                self._variable.set(serialized_values)
            finally:
                self._variable_callback_blocked = False
        self._refresh_selection_borders()

    def _focus_dropdown(self) -> None:
        self._focus_force_after_id = None
        try:
            if self._search_entry is not None and self._search_entry.winfo_exists():
                self._search_entry.focus_set()
            elif self._top_level is not None and self._top_level.winfo_exists():
                self._top_level.focus_set()
        except tk.TclError:
            pass

    def _clear_search_state(self) -> None:
        if self._search_variable is not None and self._search_trace_id is not None:
            try:
                self._search_variable.trace_remove("write", self._search_trace_id)
            except tk.TclError:
                pass
        self._search_entry = None
        self._search_variable = None
        self._search_trace_id = None

    def _on_search_changed(self, *_: Any) -> None:
        if self._top_level is None or not self._top_level.winfo_exists():
            return
        self._build_values()

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
            self._clear_search_state()
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
        self._cancel_after("_scroll_after_id")
        popup = self._top_level
        self._top_level = None
        self._selected_dropdown_button = None
        self._dropdown_value_buttons = []
        self._clear_search_state()
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
        if self._search_bar:
            self._search_variable = tk.StringVar(master=self._top_level)
            self._search_entry = Entry(
                self._top_level,
                height=30,
                bg_color=popup_backing_color,
                placeholder_text=self._search_placeholder_text,
                textvariable=self._search_variable,
            )
            self._search_entry.pack(fill="x", padx=4, pady=(4, 2))
            self._search_trace_id = self._search_variable.trace_add(
                "write",
                self._on_search_changed,
            )
        self._top_level.frame = ScrollableFrame(
            self._top_level,
            bg_color=popup_backing_color,
            fg_color=self._dropdown_fg_color,
            corner_radius=self._corner_radius,
            border_width=0,
        )
        self._top_level.frame.pack(fill="both", expand=True)
        self._build_values()
        self._top_level.update_idletasks()
        self._scroll_to_selected()
        self._top_level.geometry(f"+{int(x)}+{int(y)}")
        self._top_level.deiconify()
        self._top_level.update_idletasks()
        self._scroll_to_selected()
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
        self._selected_dropdown_button = None
        self._dropdown_value_buttons = []
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
        search_text = (
            self._search_variable.get().strip().casefold()
            if self._search_variable is not None
            else ""
        )
        visible_values = (
            [
                value
                for value in self._values
                if search_text in self._display(value).casefold()
            ]
            if search_text
            else self._values
        )
        for row, value in enumerate(visible_values):
            display_text = self._display(value)
            matches_current = self._value_matches_current(value)
            is_selected = self._show_selection and matches_current
            selected_border_color = (
                self._brighten_dropdown_color(self._dropdown_hover_color)
                if is_selected
                else "transparent"
            )
            button = Button(
                self._top_level.frame,
                width=button_width,
                text=display_text,
                text_color=self._dropdown_text_color,
                hover_color=self._dropdown_hover_color,
                fg_color="transparent",
                border_width=2,
                border_spacing=0,
                border_color=selected_border_color,
                border_hover_color=selected_border_color,
                anchor="w",
                font=self._dropdown_font,
                command=lambda selected=value: self._selected(selected),
            )
            horizontal_padding, vertical_padding = button._content_padding()
            available_text_width = max(1, button_width - horizontal_padding * 2)
            button.configure(wraplength=available_text_width)
            wrapped_text_height = (
                button._text._height if button._text is not None else 0
            )
            button.configure(
                height=max(28, wrapped_text_height + vertical_padding * 2)
            )
            button.grid(row=row, column=1, sticky="ew", padx=(2, 0))
            self._dropdown_value_buttons.append((value, button))
            if matches_current and self._selected_dropdown_button is None:
                self._selected_dropdown_button = button
        self._resize_dropdown()

    def _refresh_selection_borders(self) -> None:
        selected_border_color = self._brighten_dropdown_color(
            self._dropdown_hover_color
        )
        self._selected_dropdown_button = None
        for value, button in self._dropdown_value_buttons:
            if button._destroyed:
                continue
            matches_current = self._value_matches_current(value)
            border_color = (
                selected_border_color
                if self._show_selection and matches_current
                else "transparent"
            )
            button.configure(
                border_color=border_color,
                border_hover_color=border_color,
            )
            if matches_current and self._selected_dropdown_button is None:
                self._selected_dropdown_button = button

    def _scroll_to_selected(self) -> None:
        if self._top_level is None or self._selected_dropdown_button is None:
            return
        frame = self._top_level.frame
        frame._content._relayout_children()
        _, _, viewport_width, viewport_height = frame._viewport_geometry()
        buttons = frame.winfo_children()
        row_extent = sum(button._height for button in buttons)
        content_extent = max(viewport_height, frame._content_extent, row_extent)
        maximum = max(0, content_extent - viewport_height)
        if maximum <= 0:
            return
        button_top = 0
        for button in buttons:
            if button is self._selected_dropdown_button:
                break
            button_top += button._height
        target = round(
            max(
                0,
                min(
                    maximum,
                    button_top
                    + self._selected_dropdown_button._height / 2
                    - viewport_height / 2,
                ),
            )
        )
        frame._content_extent = content_extent
        if frame._uses_shared_viewport:
            frame._scroll_offset = target
            first = target / content_extent
            last = min(1.0, (target + viewport_height) / content_extent)
            frame._position_shared_content()
        else:
            content_width = max(viewport_width, frame._content._width)
            frame._content_canvas.configure(
                scrollregion=(
                    0,
                    0,
                    frame._apply_widget_scaling(content_width),
                    frame._apply_widget_scaling(content_extent),
                )
            )
            frame._content_canvas.yview_moveto(target / content_extent)
            first, last = frame._content_canvas.yview()
        frame._scrollbar.set(first, last)

    def _scroll_to_selected_after_open(self) -> None:
        self._scroll_after_id = None
        self._scroll_to_selected()

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
        if self._search_entry is not None:
            requested_height += (
                self._search_entry.winfo_reqheight()
                + int(round(self._apply_widget_scaling(6)))
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
        self._scroll_to_selected()
        self._cancel_after("_scroll_after_id")
        self._scroll_after_id = self.after(
            10,
            self._scroll_to_selected_after_open
        )

    def _variable_callback(self, *_: Any) -> None:
        if self._variable_callback_blocked or self._variable is None:
            return
        if self._multiple_choice:
            self._set_multiple_values(
                self._variable.get(),
                update_variable=False,
            )
        else:
            super()._variable_callback(*_)
            self._refresh_selection_borders()

    def set(self, value: Any) -> None:
        if self._multiple_choice:
            self._set_multiple_values(value)
        else:
            super().set(value)
            self._refresh_selection_borders()

    def get(self) -> Any:
        if self._multiple_choice:
            return list(self._selected_values)
        return super().get()

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        resize_dropdown = False
        rebuild_dropdown = False
        variable_configured = "variable" in kwargs
        multiple_choice = kwargs.pop("multiple_choice", None)
        search_bar = kwargs.pop("search_bar", None)
        if "dropdown_max_height" in kwargs:
            self._dropdown_max_height = self._validate_dropdown_max_height(
                kwargs.pop("dropdown_max_height")
            )
            resize_dropdown = True
        if "show_selection" in kwargs:
            show_selection = bool(kwargs.pop("show_selection"))
            if show_selection != self._show_selection:
                self._show_selection = show_selection
                rebuild_dropdown = True
        if "search_placeholder_text" in kwargs:
            self._search_placeholder_text = str(
                kwargs.pop("search_placeholder_text")
            )
            if self._search_entry is not None:
                self._search_entry.configure(
                    placeholder_text=self._search_placeholder_text
                )
        super().configure(require_redraw=require_redraw, **kwargs)
        if search_bar is not None:
            enabled = bool(search_bar)
            if enabled != self._search_bar:
                self._search_bar = enabled
                self._close_dropdown()
        if multiple_choice is not None:
            enabled = bool(multiple_choice)
            if enabled != self._multiple_choice:
                if enabled:
                    current_value = super().get()
                    self._multiple_choice = True
                    self._set_dimensions(width=self._base_width)
                    self._set_multiple_values(
                        []
                        if isinstance(current_value, str) and current_value == ""
                        else [current_value]
                    )
                else:
                    selected_values = list(self._selected_values)
                    self._multiple_choice = False
                    self._selected_values = []
                    super().set(
                        selected_values[0]
                        if selected_values
                        else (self._values[0] if self._values else "")
                    )
                    self._refresh_selection_borders()
        if self._multiple_choice and variable_configured:
            self._set_multiple_values(
                self._variable.get() if self._variable is not None else [],
                update_variable=False,
            )
        if rebuild_dropdown:
            self._build_values()
        if resize_dropdown:
            self._resize_dropdown()

    config = configure

    def cget(self, attribute_name: str) -> Any:
        if attribute_name == "dropdown_max_height":
            return self._dropdown_max_height
        if attribute_name == "show_selection":
            return self._show_selection
        if attribute_name == "multiple_choice":
            return self._multiple_choice
        if attribute_name == "search_bar":
            return self._search_bar
        if attribute_name == "search_placeholder_text":
            return self._search_placeholder_text
        return super().cget(attribute_name)

    def _selected(self, value: Any) -> None:
        if self._multiple_choice:
            selected_values = list(self._selected_values)
            matching_index = next(
                (
                    index
                    for index, selected in enumerate(selected_values)
                    if self._choices_equal(selected, value)
                ),
                None,
            )
            if matching_index is None:
                selected_values.append(value)
            else:
                selected_values.pop(matching_index)
            self._set_multiple_values(selected_values)
            if self._command is not None:
                self._command(self.get())
            return
        self._close_dropdown(restore_focus=True)
        self._dropdown_callback(value)

    def destroy(self) -> None:
        self._cancel_after("_open_after_id")
        super().destroy()


__all__ = ["ScrollableDropdown"]
