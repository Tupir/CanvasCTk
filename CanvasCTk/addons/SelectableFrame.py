from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from ..containers import Frame
from ..widgets.Label import Label


class SelectableFrame(Frame):
    """CanvasCTk port of ``CTKAddons.SelectableFrame``."""

    def __init__(
        self,
        master: Any,
        variable: Any = None,
        text: str | None = None,
        image: Any = None,
        command: Callable[["SelectableFrame"], Any] | None = None,
        text_color: Any = None,
        width: int = 0,
        height: int = 28,
        wraplength: int = 0,
        pack_propagate: bool = True,
        corner_radius: int = 10,
        **kwargs: Any,
    ) -> None:
        propagated_width = None if pack_propagate and int(width) == 0 else width
        super().__init__(
            master,
            width=propagated_width,
            height=height,
            corner_radius=corner_radius,
            **kwargs,
        )
        self.pack_propagate(pack_propagate)
        self.default_color = self.cget("fg_color")
        self.selected_color = ("#3B8ED0", "#1F6AA5")
        self.variable = variable
        self.text = text
        self.image = image
        self.command = command
        self.text_color = text_color
        self._variable_callback_name: str | None = None

        self.bind("<Button-1>", self.toggle_selection)
        if self.text:
            self.label = Label(
                self,
                text=self.text,
                font=ctk.CTkFont(weight="bold"),
                text_color=self.text_color,
                wraplength=wraplength,
            )
            self.label.pack(padx=10, pady=5, fill="both", expand=True)
            self.label.bind("<Button-1>", self.toggle_selection)
        if self.image:
            self.image_label = Label(self, image=self.image, text="")
            self.image_label.pack(pady=(0, 5))
            self.image_label.bind("<Button-1>", self.toggle_selection)

        if self.variable is not None:
            self._variable_callback_name = self.variable.trace_add("write", self.update_appearance)
            self.update_appearance()

    def toggle_selection(self, event: Any = None) -> None:
        if self.variable is not None:
            self.variable.set(not self.variable.get())
        if self.command is not None:
            self.command(self)

    def update_appearance(self, *args: Any) -> None:
        if self.variable is None:
            return
        self.configure(fg_color=self.selected_color if self.variable.get() else self.default_color)

    def destroy(self) -> None:
        if self.variable is not None and self._variable_callback_name is not None:
            try:
                self.variable.trace_remove("write", self._variable_callback_name)
            except Exception:
                pass
            self._variable_callback_name = None
        super().destroy()


__all__ = ["SelectableFrame"]
