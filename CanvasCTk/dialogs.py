from __future__ import annotations

import tkinter as tk
from collections.abc import Iterable
from typing import Any

from .containers import Frame
from .widgets import Checkbox, Button, Label
from .windows import Toplevel, Window


class Dialog(Toplevel):
    """Reusable modal dialog with buttons and optional checkbox options."""

    def __init__(
        self,
        master: Window,
        title: str = "Message",
        message: str = "",
        buttons: Iterable[str] = ("OK",),
        width: int = 520,
        height: int = 280,
        modal: bool = True,
        checkbox_options: Iterable[tuple[str, bool]] | None = None,
        default_response: str | None = None,
        close_response: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master,
            **kwargs,
        )
        self._dialog_master = master
        self._modal = bool(modal)
        self.withdraw()
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.response: str | None = default_response
        self.close_response = close_response
        self.option_vars: list[tk.BooleanVar] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        body = Frame(self, corner_radius=0)
        body.grid(row=0, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        Label(body, text=title, font=("Roboto", 22, "bold")).grid(
            row=0, column=0, padx=26, pady=(24, 10), sticky="w"
        )
        Label(body, text=message, justify="left", wraplength=max(260, width - 70)).grid(
            row=1, column=0, padx=26, pady=(4, 10), sticky="nsew"
        )

        if checkbox_options:
            options_frame = Frame(body, fg_color="transparent")
            options_frame.grid(row=2, column=0, padx=22, pady=(0, 8), sticky="ew")
            for row, (label, checked) in enumerate(checkbox_options):
                var = tk.BooleanVar(value=checked)
                self.option_vars.append(var)
                Checkbox(options_frame, text=label, variable=var).grid(row=row, column=0, padx=4, pady=3, sticky="w")

        button_frame = Frame(body, fg_color="transparent")
        button_frame.grid(row=3, column=0, padx=20, pady=(8, 20), sticky="e")
        for column, label in enumerate(buttons):
            Button(
                button_frame,
                text=label,
                width=96,
                command=lambda value=label: self.choose(value),
            ).grid(row=0, column=column, padx=5)

    @property
    def selected_options(self) -> list[bool]:
        return [var.get() for var in self.option_vars]

    def choose(self, response: str) -> None:
        self.response = response
        self.close()

    def _center_window(self) -> None:
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        self._dialog_master.update_idletasks()
        x = self._dialog_master.winfo_rootx() + (self._dialog_master.winfo_width() - width) // 2
        y = self._dialog_master.winfo_rooty() + (self._dialog_master.winfo_height() - height) // 2
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    def open(self) -> None:
        if hasattr(self._dialog_master, "add_top_level"):
            self._dialog_master.add_top_level(self)
        if self._modal:
            self.transient(self._dialog_master)
            self.grab_set()
        self._center_window()
        self.deiconify()
        self.lift()

    def ask(self) -> str | None:
        self.open()
        self.wait_window()
        return self.response

    def ask_with_options(self) -> tuple[str | None, list[bool]]:
        response = self.ask()
        return response, self.selected_options

    def close(self) -> None:
        if self.response is None:
            self.response = self.close_response
        if hasattr(self._dialog_master, "remove_top_level"):
            self._dialog_master.remove_top_level(self)
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


class MessageBox(Dialog):
    """Named alias for message-box style dialogs."""


def show_messagebox(master: Window, **kwargs: Any) -> str | None:
    """Create a ``MessageBox``, open it modally, and return the clicked button."""
    return MessageBox(master, **kwargs).ask()


def show_canvas_messagebox(master: Window, **kwargs: Any) -> str | None:
    return MessageBox(master, **kwargs).ask()
