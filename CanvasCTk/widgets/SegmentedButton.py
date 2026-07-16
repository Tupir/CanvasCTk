from __future__ import annotations

import tkinter as tk
from copy import copy
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ._ctk_port import CanvasCTkWidget, CanvasDrawEngine, CanvasDrawProxy
from ._shared import _master_background_color


class SegmentedButton(CanvasCTkWidget):
    """Canvas port of CustomTkinter's ``CTkSegmentedButton``."""

    def __init__(
        self,
        master: Any,
        width: int = 140,
        height: int = 28,
        corner_radius: int | None = None,
        border_width: int = 3,
        bg_color: Any = "transparent",
        fg_color: Any = None,
        selected_color: Any = None,
        selected_hover_color: Any = None,
        unselected_color: Any = None,
        unselected_hover_color: Any = None,
        text_color: Any = None,
        text_color_disabled: Any = None,
        background_corner_colors: Any = None,
        font: tuple | ctk.CTkFont | None = None,
        values: list[str] | tuple[str, ...] | None = None,
        variable: tk.Variable | None = None,
        dynamic_resizing: bool = True,
        command: Callable[[str], Any] | None = None,
        state: str = tk.NORMAL,
        *,
        canvas: tk.Canvas | None = None,
        x: int = 0,
        y: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, width=width, height=height, bg_color=bg_color, canvas=canvas, x=x, y=y, **kwargs)
        theme = ctk.ThemeManager.theme["CTkSegmentedButton"]
        self._sb_fg_color = self._check_color_type(theme["fg_color"] if fg_color is None else fg_color)
        self._sb_selected_color = self._check_color_type(theme["selected_color"] if selected_color is None else selected_color)
        self._sb_selected_hover_color = self._check_color_type(
            theme["selected_hover_color"] if selected_hover_color is None else selected_hover_color
        )
        self._sb_unselected_color = self._check_color_type(
            theme["unselected_color"] if unselected_color is None else unselected_color
        )
        self._sb_unselected_hover_color = self._check_color_type(
            theme["unselected_hover_color"] if unselected_hover_color is None else unselected_hover_color
        )
        self._sb_text_color = self._check_color_type(theme["text_color"] if text_color is None else text_color)
        self._sb_text_color_disabled = self._check_color_type(
            theme["text_color_disabled"] if text_color_disabled is None else text_color_disabled
        )
        self._sb_corner_radius = int(theme["corner_radius"] if corner_radius is None else corner_radius)
        self._sb_border_width = int(theme["border_width"] if border_width is None else border_width)
        self._track_theme_defaults(
            "CTkSegmentedButton",
            fg_color=fg_color is None,
            selected_color=selected_color is None,
            selected_hover_color=selected_hover_color is None,
            unselected_color=unselected_color is None,
            unselected_hover_color=unselected_hover_color is None,
            text_color=text_color is None,
            text_color_disabled=text_color_disabled is None,
            corner_radius=corner_radius is None,
            border_width=border_width is None,
        )
        self._background_corner_colors = background_corner_colors
        self._command = command
        self._font = self._coerce_font(font)
        self._font.add_size_configure_callback(self._font_changed)
        self._state = str(state)
        self._value_list = list(values if values is not None else ["CTkSegmentedButton"])
        self._check_unique_values(self._value_list)
        self._dynamic_resizing = bool(dynamic_resizing)
        self._current_value = ""
        self._hovered_value: str | None = None
        self._variable = variable
        self._variable_callback_blocked = False
        self._variable_callback_name: str | None = None
        self._segment_proxies: dict[str, CanvasDrawProxy] = {}
        self._segment_engines: dict[str, CanvasDrawEngine] = {}
        self._segment_text_ids: dict[str, int] = {}
        self._segment_width_cache: tuple[int, ...] | None = None
        self._segment_offset_cache: dict[str, tuple[int, int]] = {}
        self._segment_total_width_cache = 0
        self._segment_metrics_revision = 0
        self._next_segment_id = 0
        self._surface_proxy = self._canvas.scoped("segmented-surface")
        self._surface_engine = CanvasDrawEngine(self, self._surface_proxy)

        if self._variable is not None:
            self._variable_callback_name = self._variable.trace_add("write", self._variable_callback)
            self.set(self._variable.get(), from_variable_callback=True)
        self._draw()

    @staticmethod
    def _coerce_font(font: tuple | ctk.CTkFont | None) -> ctk.CTkFont:
        if isinstance(font, ctk.CTkFont):
            return font
        if font is None:
            return ctk.CTkFont()
        options: dict[str, Any] = {"family": font[0], "size": int(font[1])}
        if len(font) > 2:
            options["weight"] = font[2]
        return ctk.CTkFont(**options)

    def _font_changed(self) -> None:
        self._invalidate_segment_metrics()
        self._draw()

    def _invalidate_segment_metrics(self) -> None:
        self._segment_width_cache = None
        self._segment_offset_cache = {}
        self._segment_total_width_cache = 0
        self._segment_metrics_revision += 1

    @staticmethod
    def _check_unique_values(values: list[str]) -> None:
        if len(values) != len(set(values)):
            raise ValueError("CTkSegmentedButton values are not unique")

    def _segment_widths(self) -> list[int]:
        if not self._value_list:
            return []
        if self._segment_width_cache is not None:
            return list(self._segment_width_cache)
        if self._dynamic_resizing:
            widths = [max(self._current_height, self._font.measure(value) + 16) for value in self._value_list]
            total = sum(widths)
            # Dynamic content may expand the rendered widget, but CTk's cget
            # continues to report the configured/designed width.
            self._current_width = self._width = total
        else:
            base, remainder = divmod(self._current_width, len(self._value_list))
            widths = [base + (1 if index < remainder else 0) for index in range(len(self._value_list))]
        self._segment_width_cache = tuple(widths)
        offset = 0
        self._segment_offset_cache = {}
        for value, width in zip(self._value_list, widths):
            self._segment_offset_cache[value] = (offset, offset + width)
            offset += width
        self._segment_total_width_cache = offset
        return widths

    def _segment_total_width(self) -> int:
        self._segment_widths()
        return self._segment_total_width_cache

    def _segment_bounds(self, value: str) -> tuple[int, int] | None:
        self._segment_widths()
        return self._segment_offset_cache.get(value)

    def _segment_fill(self, value: str) -> Any:
        selected = value == self._current_value
        hovered = value == self._hovered_value and self._state == tk.NORMAL
        if selected:
            color = self._sb_selected_hover_color if hovered else self._sb_selected_color
        else:
            color = self._sb_unselected_hover_color if hovered else self._sb_unselected_color
        return self._apply_appearance_mode(color)

    def _refresh_segment_fill(self, value: str) -> None:
        proxy = self._segment_proxies.get(value)
        if proxy is None:
            return
        fill = self._segment_fill(value)
        proxy.itemconfig("inner_parts", fill=fill, outline=fill)

    def _refresh_all_segment_fills(self) -> None:
        for value in self._value_list:
            self._refresh_segment_fill(value)

    def _refresh_text_colors(self) -> None:
        color = self._sb_text_color_disabled if self._state == tk.DISABLED else self._sb_text_color
        fill = self._apply_appearance_mode(color)
        for text_id in self._segment_text_ids.values():
            self._canvas.itemconfig(text_id, fill=fill)

    def _refresh_surface_colors(self) -> None:
        surface = self._apply_appearance_mode(self._sb_fg_color)
        self._surface_proxy.itemconfig("border_parts", fill=surface, outline=surface)
        self._surface_proxy.itemconfig("inner_parts", fill=surface, outline=surface)
        for proxy in self._segment_proxies.values():
            proxy.itemconfig("border_parts", fill=surface, outline=surface)

    def _clear_segments(self) -> None:
        for proxy in self._segment_proxies.values():
            proxy.destroy_all()
        self._segment_proxies.clear()
        self._segment_engines.clear()
        self._segment_text_ids.clear()

    def _discard_removed_segments(self, valid: set[str]) -> None:
        """Delete only segments no longer present and retain reusable items."""
        for value in tuple(self._segment_proxies):
            if value in valid:
                continue
            self._segment_proxies.pop(value).destroy_all()
            self._segment_engines.pop(value, None)
            self._segment_text_ids.pop(value, None)

    def _ensure_segment(self, value: str, x_offset: int) -> tuple[CanvasDrawProxy, CanvasDrawEngine, int]:
        proxy = self._segment_proxies.get(value)
        if proxy is None:
            proxy = self._canvas.scoped(f"segment-{self._next_segment_id}", x=x_offset)
            self._next_segment_id += 1
            engine = CanvasDrawEngine(self, proxy)
            text_id = proxy.create_text(0, 0, anchor="center")
            proxy.bind("<Enter>", lambda _event, selected=value: self._on_segment_enter(selected), add="+")
            proxy.bind("<Leave>", lambda _event, selected=value: self._on_segment_leave(selected), add="+")
            proxy.bind("<Button-1>", lambda _event, selected=value: self._on_segment_click(selected), add="+")
            self._segment_proxies[value] = proxy
            self._segment_engines[value] = engine
            self._segment_text_ids[value] = text_id
        else:
            proxy._origin_offset = (x_offset, 0)
            self._segment_engines[value]._canvas._origin_offset = proxy._origin_offset
        return proxy, self._segment_engines[value], self._segment_text_ids[value]

    def _draw(self, *_: Any, no_color_updates: bool = False) -> None:
        if not self._value_list:
            self._clear_segments()
            self._surface_proxy.destroy_all()
            return

        widths = self._segment_widths()
        valid = set(self._value_list)
        self._discard_removed_segments(valid)

        if self._background_corner_colors is not None:
            if (
                not isinstance(self._background_corner_colors, (tuple, list))
                or len(self._background_corner_colors) != 4
            ):
                raise ValueError("background_corner_colors must contain four colors")
            self._surface_engine.draw_background_corners(
                self._current_width,
                self._current_height,
            )
            for tag, color in zip(
                (
                    "background_corner_top_left",
                    "background_corner_top_right",
                    "background_corner_bottom_right",
                    "background_corner_bottom_left",
                ),
                self._background_corner_colors,
            ):
                self._surface_proxy.itemconfig(
                    tag,
                    fill=self._apply_appearance_mode(color),
                    outline=self._apply_appearance_mode(color),
                )
        else:
            self._surface_proxy.delete("background_parts")

        self._surface_engine.draw_rounded_rect_with_border(
            self._current_width,
            self._current_height,
            self._sb_corner_radius,
            0,
        )
        surface = self._apply_appearance_mode(self._sb_fg_color)
        self._surface_proxy.itemconfig("border_parts", fill=surface, outline=surface)
        self._surface_proxy.itemconfig("inner_parts", fill=surface, outline=surface)

        x_offset = 0
        text_color = self._sb_text_color_disabled if self._state == tk.DISABLED else self._sb_text_color
        for value, width in zip(self._value_list, widths):
            proxy, engine, text_id = self._ensure_segment(value, x_offset)
            engine.draw_rounded_rect_with_border(
                width,
                self._current_height,
                self._sb_corner_radius,
                self._sb_border_width,
            )
            fill = self._segment_fill(value)
            proxy.itemconfig("border_parts", fill=surface, outline=surface)
            proxy.itemconfig("inner_parts", fill=fill, outline=fill)
            proxy.coords(text_id, width / 2, self._current_height / 2)
            proxy.itemconfig(text_id, text=value, font=self._font, fill=self._apply_appearance_mode(text_color))
            self.canvas.tag_raise(text_id)
            x_offset += width

    def _variable_callback(self, *_: Any) -> None:
        if not self._variable_callback_blocked and self._variable is not None:
            self.set(self._variable.get(), from_variable_callback=True)

    def _on_segment_enter(self, value: str) -> None:
        if self._state == tk.NORMAL:
            previous = self._hovered_value
            self._hovered_value = value
            self.canvas.configure(cursor="hand2")
            if previous is not None and previous != value:
                self._refresh_segment_fill(previous)
            self._refresh_segment_fill(value)

    def _on_segment_leave(self, value: str) -> None:
        if self._hovered_value == value:
            self._hovered_value = None
            self.canvas.configure(cursor="")
            self._refresh_segment_fill(value)

    def _on_segment_click(self, value: str) -> None:
        if self._state == tk.NORMAL:
            self.set(value, from_button_callback=True)

    def set(self, value: str, from_variable_callback: bool = False, from_button_callback: bool = False) -> None:
        if value == self._current_value:
            return
        previous = self._current_value
        self._current_value = value
        if self._variable is not None and not from_variable_callback:
            self._variable_callback_blocked = True
            self._variable.set(value)
            self._variable_callback_blocked = False
        if previous:
            self._refresh_segment_fill(previous)
        if value:
            self._refresh_segment_fill(value)
        if from_button_callback and self._command is not None:
            self._command(self._current_value)

    def get(self) -> str:
        return self._current_value

    def index(self, value: str) -> int:
        return self._value_list.index(value)

    def insert(self, index: int, value: str) -> None:
        if not value:
            raise ValueError("CTkSegmentedButton can not insert value ''")
        if value in self._value_list:
            raise ValueError(f"CTkSegmentedButton can not insert value {value!r}, already part of the values")
        self._value_list.insert(index, value)
        self._invalidate_segment_metrics()
        self._draw()

    def move(self, new_index: int, value: int | str) -> None:
        if isinstance(value, int):
            super().move(new_index, value)
            return
        if not 0 <= new_index < len(self._value_list):
            raise ValueError(f"CTkSegmentedButton new_index {new_index} not in range")
        old_index = self._value_list.index(value)
        self._value_list.pop(old_index)
        self._value_list.insert(new_index, value)
        self._invalidate_segment_metrics()
        self._draw()

    def delete(self, value: str) -> None:
        if value not in self._value_list:
            raise ValueError(f"CTkSegmentedButton does not contain value {value!r}")
        self._value_list.remove(value)
        self._invalidate_segment_metrics()
        if self._current_value == value:
            self._current_value = ""
        self._draw()

    def _set_dimensions(self, width: int | None = None, height: int | None = None) -> bool:
        width_changed = width is not None and max(1, int(width)) != self._desired_width
        height_changed = height is not None and max(1, int(height)) != self._desired_height
        if not width_changed and not height_changed:
            return False
        self._invalidate_segment_metrics()
        return super()._set_dimensions(
            width if width_changed else None,
            height if height_changed else None,
        )

    def _on_widget_scaling_changed(self, old_scaling: float, new_scaling: float) -> None:
        if old_scaling != new_scaling:
            self._invalidate_segment_metrics()
        super()._on_widget_scaling_changed(old_scaling, new_scaling)

    def _resize_for_place(self, width: int | None, height: int | None) -> None:
        effective_width = (
            self._segment_total_width()
            if self._dynamic_resizing and width is None and self._value_list
            else width
        )
        target_width = self._desired_width if effective_width is None else max(1, int(effective_width))
        target_height = self._desired_height if height is None else max(1, int(height))
        if target_width != self._current_width or target_height != self._current_height:
            self._invalidate_segment_metrics()
        super()._resize_for_place(effective_width, height)

    def configure(self, **kwargs: Any) -> None:
        width = kwargs.pop("width", None)
        height = kwargs.pop("height", None)
        full_redraw = False
        refresh_surface = False
        refresh_fills = False
        refresh_selection = False
        refresh_text = False
        old_current = self._current_value
        aliases = {
            "corner_radius": "_sb_corner_radius",
            "border_width": "_sb_border_width",
            "fg_color": "_sb_fg_color",
            "selected_color": "_sb_selected_color",
            "selected_hover_color": "_sb_selected_hover_color",
            "unselected_color": "_sb_unselected_color",
            "unselected_hover_color": "_sb_unselected_hover_color",
            "text_color": "_sb_text_color",
            "text_color_disabled": "_sb_text_color_disabled",
            "background_corner_colors": "_background_corner_colors",
            "command": "_command",
            "state": "_state",
        }
        for name, attribute in aliases.items():
            if name in kwargs:
                value = kwargs.pop(name)
                if name.endswith("color"):
                    value = self._check_color_type(value)
                elif name in {"corner_radius", "border_width"}:
                    value = int(value)
                elif name == "state":
                    value = str(value)
                if getattr(self, attribute) == value:
                    continue
                setattr(self, attribute, value)
                if name in {"corner_radius", "border_width", "background_corner_colors"}:
                    full_redraw = True
                elif name == "fg_color":
                    refresh_surface = True
                elif name in {"selected_color", "selected_hover_color", "unselected_color", "unselected_hover_color"}:
                    refresh_fills = True
                elif name in {"text_color", "text_color_disabled"}:
                    refresh_text = True
                elif name == "state":
                    refresh_fills = refresh_text = True
                    if self._state != tk.NORMAL:
                        self.canvas.configure(cursor="")
        if "font" in kwargs:
            new_font = self._coerce_font(kwargs.pop("font"))
            if new_font is not self._font:
                self._font.remove_size_configure_callback(self._font_changed)
                self._font = new_font
                self._font.add_size_configure_callback(self._font_changed)
                self._invalidate_segment_metrics()
                full_redraw = True
        if "values" in kwargs:
            values = list(kwargs.pop("values"))
            self._check_unique_values(values)
            if values != self._value_list:
                self._value_list = values
                self._invalidate_segment_metrics()
                full_redraw = True
                if self._current_value not in values:
                    self._current_value = ""
                if self._hovered_value not in values:
                    self._hovered_value = None
        if "variable" in kwargs:
            variable = kwargs.pop("variable")
            if variable is not self._variable:
                if self._variable is not None and self._variable_callback_name is not None:
                    self._variable.trace_remove("write", self._variable_callback_name)
                self._variable = variable
                self._variable_callback_name = None
                if self._variable is not None:
                    self._variable_callback_name = self._variable.trace_add("write", self._variable_callback)
                    self._current_value = self._variable.get()
                refresh_selection = True
        if "dynamic_resizing" in kwargs:
            dynamic_resizing = bool(kwargs.pop("dynamic_resizing"))
            if dynamic_resizing != self._dynamic_resizing:
                self._dynamic_resizing = dynamic_resizing
                self._invalidate_segment_metrics()
                full_redraw = True

        dimensions_redrawn = False
        if width is not None or height is not None:
            dimensions_redrawn = self._set_dimensions(width=width, height=height)
        base_redraw = False
        if "bg_color" in kwargs:
            checked = self._check_color_type(kwargs["bg_color"], transparency=True)
            resolved = _master_background_color(self.master, self.canvas) if checked == "transparent" else checked
            base_redraw = resolved != self._bg_color
        super().configure(**kwargs)

        if full_redraw and not dimensions_redrawn and not base_redraw:
            self._draw()
            return
        if full_redraw or dimensions_redrawn or base_redraw:
            return
        if refresh_surface:
            self._refresh_surface_colors()
        if refresh_fills:
            if old_current and old_current != self._current_value:
                self._refresh_segment_fill(old_current)
            self._refresh_all_segment_fills()
        elif refresh_selection:
            if old_current:
                self._refresh_segment_fill(old_current)
            if self._current_value:
                self._refresh_segment_fill(self._current_value)
        if refresh_text:
            self._refresh_text_colors()

    config = configure

    def bind(self, sequence: Any = None, command: Any = None, add: Any = None) -> None:
        raise NotImplementedError

    def unbind(self, sequence: Any = None, funcid: Any = None) -> None:
        raise NotImplementedError

    def cget(self, attribute_name: str) -> Any:
        values = {
            "corner_radius": self._sb_corner_radius,
            "border_width": self._sb_border_width,
            "fg_color": self._sb_fg_color,
            "selected_color": self._sb_selected_color,
            "selected_hover_color": self._sb_selected_hover_color,
            "unselected_color": self._sb_unselected_color,
            "unselected_hover_color": self._sb_unselected_hover_color,
            "text_color": self._sb_text_color,
            "text_color_disabled": self._sb_text_color_disabled,
            "background_corner_colors": self._background_corner_colors,
            "font": self._font,
            "values": copy(self._value_list),
            "variable": self._variable,
            "dynamic_resizing": self._dynamic_resizing,
            "command": self._command,
            "state": self._state,
        }
        return values[attribute_name] if attribute_name in values else super().cget(attribute_name)

    def destroy(self) -> None:
        self._font.remove_size_configure_callback(self._font_changed)
        if self._variable is not None and self._variable_callback_name is not None:
            self._variable.trace_remove("write", self._variable_callback_name)
        super().destroy()


__all__ = ["SegmentedButton"]
