from __future__ import annotations

import sys
from typing import Any, Callable

import customtkinter as ctk
from PIL import ImageEnhance

from ..widgets.Label import Label


class LabelButton(Label):
    """Canvas-native port of ``CTKAddons.LabelButton``."""

    def __init__(
        self,
        master: Any,
        width: int = 140,
        height: int = 28,
        variable: Any = None,
        text: str | None = None,
        image: ctk.CTkImage | None = None,
        command: Callable[[], Any] | None = None,
        text_color: Any = None,
        hover: bool = True,
        **kwargs: Any,
    ) -> None:
        self._state = ctk.NORMAL
        self._hover = bool(hover)
        self._click_animation_running = False
        self._command = command
        super().__init__(
            master,
            width=width,
            height=height,
            text=text,
            image=image,
            text_color=text_color,
            **kwargs,
        )
        self.default_color = self.cget("fg_color")
        self.selected_color = ("#3B8ED0", "#1F6AA5")
        self.variable = variable
        self.text = text
        self.image = image
        self._image_variants: dict[float, ctk.CTkImage | None] = {1.0: image}
        self.text_color = text_color
        self._variable_callback_name: str | None = None

        self.bind("<Button-1>", self._clicked)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        if self.variable is not None:
            self._variable_callback_name = self.variable.trace_add("write", self.update_appearance)
            self.update_appearance()

    @staticmethod
    def darken_image(ctk_image: ctk.CTkImage | None, darkness: float = 0.65) -> ctk.CTkImage | None:
        if ctk_image is None:
            return None
        try:
            light_image = ctk_image.cget("light_image")
            dark_image = ctk_image.cget("dark_image")
            size = ctk_image.cget("size")
        except Exception:
            light_image = ctk_image._light_image
            dark_image = ctk_image._dark_image
            size = ctk_image._size

        if light_image is not None:
            light_image = ImageEnhance.Brightness(light_image).enhance(darkness)
        if dark_image is not None:
            dark_image = ImageEnhance.Brightness(dark_image).enhance(darkness)
        return ctk.CTkImage(light_image=light_image, dark_image=dark_image, size=size)

    def _set_cursor(self, hovering: bool = False) -> None:
        if self._state == ctk.DISABLED or self._command is None:
            cursor = ""
        elif sys.platform == "darwin":
            cursor = "pointinghand"
        elif sys.platform.startswith("win"):
            cursor = "hand2"
        else:
            cursor = "hand2"
        if hovering:
            self.canvas.configure(cursor=cursor)

    def _on_enter(self, event: Any = None) -> None:
        if self._hover and self._state == ctk.NORMAL:
            self._set_cursor(hovering=True)
            if self.image is not None:
                hover_image = self._image_variants.get(0.5)
                if hover_image is None:
                    hover_image = self.darken_image(self.image, 0.5)
                    self._image_variants[0.5] = hover_image
                super().configure(image=hover_image)

    def _on_leave(self, event: Any = None) -> None:
        self._click_animation_running = False
        self.canvas.configure(cursor="")
        if self.image is not None:
            super().configure(image=self.image)

    def _click_animation(self) -> None:
        if self._click_animation_running:
            self._on_enter()

    def _clicked(self, event: Any = None) -> None:
        if self._state == ctk.DISABLED:
            return
        self._on_leave()
        self._click_animation_running = True
        self.after(100, self._click_animation)
        if self._command is not None:
            self._command()

    def update_appearance(self, *args: Any) -> None:
        if self.variable is None:
            return
        self.configure(fg_color=self.selected_color if self.variable.get() else self.default_color)

    def configure(self, require_redraw: bool = False, **kwargs: Any) -> None:
        if "image" in kwargs:
            self.image = kwargs["image"]
            self._image_variants = {1.0: self.image}
        if "state" in kwargs:
            self._state = str(kwargs.pop("state"))
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if "hover" in kwargs:
            self._hover = bool(kwargs.pop("hover"))
        super().configure(require_redraw=require_redraw, **kwargs)

    config = configure

    def cget(self, attribute_name: str) -> Any:
        values = {
            "state": self._state,
            "command": self._command,
            "hover": self._hover,
        }
        return values[attribute_name] if attribute_name in values else super().cget(attribute_name)

    def destroy(self) -> None:
        if self.variable is not None and self._variable_callback_name is not None:
            try:
                self.variable.trace_remove("write", self._variable_callback_name)
            except Exception:
                pass
            self._variable_callback_name = None
        super().destroy()


__all__ = ["LabelButton"]
