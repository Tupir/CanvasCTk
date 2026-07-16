from __future__ import annotations

import sys
import tkinter as tk
from typing import Any, Callable

import customtkinter as ctk

from ._ctk_port import CanvasCTkWidget, CanvasDrawEngine


class Switch(CanvasCTkWidget):
    """Canvas port of CustomTkinter's ``CTkSwitch``."""

    _TEXT_SPACING = 6

    def __init__(
        self,
        master: Any,
        width: int = 100,
        height: int = 24,
        switch_width: int = 36,
        switch_height: int = 18,
        corner_radius: int | None = None,
        border_width: int | None = None,
        button_length: int | None = None,
        bg_color: Any = "transparent",
        fg_color: Any = None,
        border_color: Any = "transparent",
        progress_color: Any = None,
        button_color: Any = None,
        button_hover_color: Any = None,
        text_color: Any = None,
        text_color_disabled: Any = None,
        text: str = "CTkSwitch",
        font: tuple | ctk.CTkFont | None = None,
        textvariable: tk.Variable | None = None,
        onvalue: int | str = 1,
        offvalue: int | str = 0,
        variable: tk.Variable | None = None,
        hover: bool = True,
        command: Callable[[], Any] | None = None,
        state: str = tk.NORMAL,
        *,
        canvas: tk.Canvas | None = None,
        x: int = 0,
        y: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, width=width, height=height, bg_color=bg_color, canvas=canvas, x=x, y=y, **kwargs)
        # Native CTk renders the switch control in its own canvas, centered in
        # the widget's grid row.  Keep the DrawEngine shapes on an equivalent
        # scoped surface so taller fonts do not leave the control pinned to the
        # top while the text is centered lower down.
        self._switch_canvas = self._canvas.scoped("switch")
        self._draw_engine = CanvasDrawEngine(self, self._switch_canvas)
        # CTkSwitch is a propagating Tk frame: its requested size is at least
        # the configured size, but long text (or a taller font) expands that
        # request.  The canvas port draws the same text directly on the shared
        # canvas, so keep a separate content-driven request for geometry
        # managers instead of reporting only the fixed 100x24 fallback.
        self._auto_width = True
        self._auto_height = True
        self._requested_width = self._desired_width
        self._requested_height = self._desired_height
        theme = ctk.ThemeManager.theme["CTkSwitch"]
        self._switch_width = int(switch_width)
        self._switch_height = int(switch_height)
        self._border_color = self._check_color_type(border_color, transparency=True)
        self._fg_color = theme["fg_color"] if fg_color is None else self._check_color_type(fg_color)
        self._progress_color = theme["progress_color"] if progress_color is None else self._check_color_type(progress_color, transparency=True)
        self._button_color = theme["button_color"] if button_color is None else self._check_color_type(button_color)
        self._button_hover_color = theme["button_hover_color"] if button_hover_color is None else self._check_color_type(button_hover_color)
        self._text_color = theme["text_color"] if text_color is None else self._check_color_type(text_color)
        self._text_color_disabled = theme["text_color_disabled"] if text_color_disabled is None else self._check_color_type(text_color_disabled)
        self._text = "" if text is None else str(text)
        self._font = self._coerce_font(font)
        self._textvariable = textvariable
        self._text_id: int | None = None
        self._corner_radius = theme["corner_radius"] if corner_radius is None else int(corner_radius)
        self._border_width = theme["border_width"] if border_width is None else int(border_width)
        self._button_length = theme["button_length"] if button_length is None else int(button_length)
        self._track_theme_defaults(
            "CTkSwitch",
            fg_color=fg_color is None,
            progress_color=progress_color is None,
            button_color=button_color is None,
            button_hover_color=button_hover_color is None,
            text_color=text_color is None,
            text_color_disabled=text_color_disabled is None,
            corner_radius=corner_radius is None,
            border_width=border_width is None,
            button_length=button_length is None,
        )
        self._hover_state = False
        self._check_state = variable is not None and variable != "" and variable.get() == onvalue
        self._hover = bool(hover)
        self._state = state
        self._onvalue = onvalue
        self._offvalue = offvalue
        self._command = command
        self._variable = variable
        self._variable_callback_blocked = False
        self._variable_callback_name: str | None = None
        self._textvariable_callback_name: str | None = None
        self._create_bindings()
        self._set_cursor()
        if self._variable is not None and self._variable != "":
            self._variable_callback_name = self._variable.trace_add("write", self._variable_callback)
        if self._textvariable is not None and self._textvariable != "":
            self._textvariable_callback_name = self._textvariable.trace_add("write", self._textvariable_callback)
            self._text = str(self._textvariable.get())
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

    def _create_bindings(self, sequence: str | None = None) -> None:
        if sequence is None or sequence == "<Enter>":
            self._canvas.bind("<Enter>", self._on_enter, add="+")
        if sequence is None or sequence == "<Leave>":
            self._canvas.bind("<Leave>", self._on_leave, add="+")
        if sequence is None or sequence == "<Button-1>":
            self._canvas.bind("<Button-1>", self.toggle, add="+")

    def _set_cursor(self) -> None:
        if not self._cursor_manipulation_enabled:
            return
        self.canvas.configure(cursor=("arrow" if self._state == tk.DISABLED else "pointinghand" if sys.platform == "darwin" else "hand2"))

    def _draw(self, no_color_updates: bool = False) -> None:
        switch_offset = (
            0,
            max(0, (self._current_height - self._switch_height) / 2),
        )
        self._switch_canvas._origin_offset = switch_offset
        self._draw_engine._canvas._origin_offset = switch_offset
        requires_recoloring = self._draw_engine.draw_rounded_slider_with_border_and_button(
            self._switch_width,
            self._switch_height,
            self._corner_radius,
            self._border_width,
            self._button_length,
            self._corner_radius,
            1 if self._check_state else 0,
            "w",
        )
        if no_color_updates and not requires_recoloring:
            return
        self._refresh_switch_colors()
        self._refresh_text()

    def _refresh_switch_colors(self) -> None:
        border = self._apply_appearance_mode(self._bg_color if self._border_color == "transparent" else self._border_color)
        foreground = self._apply_appearance_mode(self._fg_color)
        progress = foreground if self._progress_color == "transparent" else self._apply_appearance_mode(self._progress_color)
        self._switch_canvas.itemconfig("border_parts", fill=border, outline=border)
        self._switch_canvas.itemconfig("inner_parts", fill=foreground, outline=foreground)
        self._switch_canvas.itemconfig("progress_parts", fill=progress, outline=progress)
        self._refresh_thumb_color()
        self._switch_canvas.tag_raise("progress_parts", "inner_parts")
        self._switch_canvas.tag_raise("slider_parts", "progress_parts")

    def _refresh_thumb_color(self) -> None:
        thumb = self._apply_appearance_mode(self._button_hover_color if self._hover_state else self._button_color)
        self._switch_canvas.itemconfig("slider_parts", fill=thumb, outline=thumb)

    def _refresh_text(self) -> None:
        text_color = self._text_color_disabled if self._state == tk.DISABLED else self._text_color
        text_x = self._switch_width + self._TEXT_SPACING
        text_y = self._current_height / 2
        if self._text_id is None:
            self._text_id = self._canvas.create_text(
                text_x,
                text_y,
                anchor="w",
                text=self._text,
                font=self._font,
                fill=self._apply_appearance_mode(text_color),
            )
        else:
            self._canvas.coords(self._text_id, text_x, text_y)
            self._canvas.itemconfig(
                self._text_id,
                text=self._text,
                font=self._font,
                fill=self._apply_appearance_mode(text_color),
                state="normal",
            )
        self._align_text_to_switch()
        self._refresh_requested_size()

    def _align_text_to_switch(self) -> None:
        """Center the rendered text bbox on the rendered switch-track bbox."""
        if self._text_id is None or not self._is_rendered:
            return
        switch_bounds = self.canvas.bbox(self._switch_canvas._root_tag)
        text_bounds = self.canvas.bbox(self._text_id)
        if switch_bounds is None or text_bounds is None:
            return
        switch_center = (switch_bounds[1] + switch_bounds[3]) / 2
        text_center = (text_bounds[1] + text_bounds[3]) / 2
        offset = switch_center - text_center
        if offset:
            self.canvas.move(self._text_id, 0, offset)

    def _refresh_requested_size(self) -> None:
        text_width = text_height = 0
        if self._text_id is not None and self._text:
            was_hidden = self.canvas.itemcget(self._text_id, "state") == "hidden"
            if was_hidden:
                self.canvas.itemconfigure(self._text_id, state="normal")
            bounds = self.canvas.bbox(self._text_id)
            if was_hidden:
                self.canvas.itemconfigure(self._text_id, state="hidden")
            if bounds is not None:
                text_width = int(round(self._reverse_widget_scaling(bounds[2] - bounds[0])))
                text_height = int(round(self._reverse_widget_scaling(bounds[3] - bounds[1])))

        requested_width = max(
            self._desired_width,
            self._switch_width + (self._TEXT_SPACING + text_width if text_width else 0),
        )
        requested_height = max(self._desired_height, self._switch_height, text_height)
        if (requested_width, requested_height) == (self._requested_width, self._requested_height):
            return
        self._requested_width = requested_width
        self._requested_height = requested_height
        if self._canvas_host is not None and self._layout_manager:
            self._canvas_host._schedule_child_layout()
        elif self._layout_manager:
            self._schedule_canvas_layout()

    def _resize_for_place(self, width: int | None, height: int | None) -> None:
        # With no fill/sticky override, Tk allocates the widget's propagated
        # request, not merely the configured width/height fallback.
        target_width = self._requested_width if width is None else max(1, int(width))
        target_height = self._requested_height if height is None else max(1, int(height))
        changed = False
        if target_width != self._current_width:
            self._current_width = self._width = target_width
            changed = True
        if target_height != self._current_height:
            self._current_height = self._height = target_height
            changed = True
        if changed:
            self._draw()

    def _show(self) -> None:
        super()._show()
        self._align_text_to_switch()

    def winfo_reqwidth(self) -> int:
        return max(1, int(round(self._apply_widget_scaling(self._requested_width))))

    def winfo_reqheight(self) -> int:
        return max(1, int(round(self._apply_widget_scaling(self._requested_height))))

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        refresh_switch = False
        refresh_thumb = False
        refresh_text = False
        for option in ("corner_radius", "border_width", "button_length", "switch_width", "switch_height"):
            if option in kwargs:
                setattr(self, f"_{option}", int(kwargs.pop(option)))
                require_redraw = True
        if "text" in kwargs:
            value = kwargs.pop("text")
            self._text = "" if value is None else str(value)
            refresh_text = True
        if "font" in kwargs:
            self._font = self._coerce_font(kwargs.pop("font"))
            refresh_text = True
        for option in ("fg_color", "border_color", "progress_color", "button_color", "button_hover_color", "text_color", "text_color_disabled"):
            if option in kwargs:
                transparency = option in ("border_color", "progress_color")
                setattr(self, f"_{option}", self._check_color_type(kwargs.pop(option), transparency=transparency))
                if option in {"text_color", "text_color_disabled"}:
                    refresh_text = True
                elif option in {"button_color", "button_hover_color"}:
                    refresh_thumb = True
                else:
                    refresh_switch = True
        if "state" in kwargs:
            self._state = kwargs.pop("state")
            self._set_cursor()
            if self._state == tk.DISABLED and self._hover_state:
                self._hover_state = False
                refresh_thumb = True
            refresh_text = True
        if "hover" in kwargs:
            self._hover = bool(kwargs.pop("hover"))
            if not self._hover and self._hover_state:
                self._hover_state = False
                refresh_thumb = True
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if "textvariable" in kwargs:
            if self._textvariable is not None and self._textvariable_callback_name is not None:
                self._textvariable.trace_remove("write", self._textvariable_callback_name)
            self._textvariable = kwargs.pop("textvariable")
            self._textvariable_callback_name = None
            if self._textvariable is not None and self._textvariable != "":
                self._textvariable_callback_name = self._textvariable.trace_add("write", self._textvariable_callback)
                self._text = str(self._textvariable.get())
            refresh_text = True
        if "variable" in kwargs:
            if self._variable is not None and self._variable_callback_name is not None:
                self._variable.trace_remove("write", self._variable_callback_name)
            self._variable = kwargs.pop("variable")
            self._variable_callback_name = None
            if self._variable is not None and self._variable != "":
                self._variable_callback_name = self._variable.trace_add("write", self._variable_callback)
                checked = self._variable.get() == self._onvalue
                if checked != self._check_state:
                    self._check_state = checked
                    require_redraw = True
            else:
                self._variable = None
        super().configure(require_redraw=require_redraw, **kwargs)
        if not require_redraw:
            if refresh_switch:
                self._refresh_switch_colors()
            elif refresh_thumb:
                self._refresh_thumb_color()
            if refresh_text:
                self._refresh_text()

    config = configure

    def cget(self, attribute_name: str) -> Any:
        values = {
            "corner_radius": self._corner_radius, "border_width": self._border_width,
            "button_length": self._button_length, "switch_width": self._switch_width,
            "switch_height": self._switch_height, "fg_color": self._fg_color,
            "border_color": self._border_color, "progress_color": self._progress_color,
            "button_color": self._button_color, "button_hover_color": self._button_hover_color,
            "text_color": self._text_color, "text_color_disabled": self._text_color_disabled,
            "text": self._text, "font": self._font, "textvariable": self._textvariable,
            "onvalue": self._onvalue, "offvalue": self._offvalue, "variable": self._variable,
            "hover": self._hover, "command": self._command, "state": self._state,
        }
        return values[attribute_name] if attribute_name in values else super().cget(attribute_name)

    def toggle(self, _event: Any = None) -> None:
        if self._state == tk.DISABLED:
            return
        self._check_state = not self._check_state
        self._draw(no_color_updates=True)
        if self._variable is not None:
            self._variable_callback_blocked = True
            self._variable.set(self._onvalue if self._check_state else self._offvalue)
            self._variable_callback_blocked = False
        if self._command is not None:
            self._command()

    def select(self, from_variable_callback: bool = False) -> None:
        if self._state != tk.DISABLED or from_variable_callback:
            if not self._check_state:
                self._check_state = True
                self._draw(no_color_updates=True)
            if self._variable is not None and not from_variable_callback:
                self._variable_callback_blocked = True
                self._variable.set(self._onvalue)
                self._variable_callback_blocked = False

    def deselect(self, from_variable_callback: bool = False) -> None:
        if self._state != tk.DISABLED or from_variable_callback:
            if self._check_state:
                self._check_state = False
                self._draw(no_color_updates=True)
            if self._variable is not None and not from_variable_callback:
                self._variable_callback_blocked = True
                self._variable.set(self._offvalue)
                self._variable_callback_blocked = False

    def get(self) -> int | str:
        return self._onvalue if self._check_state else self._offvalue

    def _on_enter(self, _event: Any = None) -> None:
        if self._hover and self._state == tk.NORMAL and not self._hover_state:
            self._hover_state = True
            self._refresh_thumb_color()

    def _on_leave(self, _event: Any = None) -> None:
        if not self._hover_state:
            return
        self._hover_state = False
        self._refresh_thumb_color()

    def _variable_callback(self, *_: Any) -> None:
        if self._variable_callback_blocked or self._variable is None:
            return
        if self._variable.get() == self._onvalue:
            self.select(from_variable_callback=True)
        elif self._variable.get() == self._offvalue:
            self.deselect(from_variable_callback=True)

    def _textvariable_callback(self, *_: Any) -> None:
        if self._textvariable is not None:
            self._text = str(self._textvariable.get())
            self._refresh_text()

    def unbind(self, sequence: str | None = None, funcid: str | None = None) -> Any:
        if self._is_lifecycle_event(sequence):
            return self._unbind_lifecycle_event(sequence, funcid)
        if funcid is not None:
            raise ValueError("'funcid' must be None to preserve internal callbacks")
        result = self._canvas.unbind(sequence)
        self._create_bindings(sequence)
        return result

    def destroy(self) -> None:
        if self._variable is not None and self._variable_callback_name is not None:
            self._variable.trace_remove("write", self._variable_callback_name)
        if self._textvariable is not None and self._textvariable_callback_name is not None:
            self._textvariable.trace_remove("write", self._textvariable_callback_name)
        super().destroy()


__all__ = ["Switch"]
