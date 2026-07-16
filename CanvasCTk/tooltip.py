from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Any


class ToolTip:
    """Dependency-free tooltip with cursor following and root-window clamping."""

    def __init__(
        self,
        widget: Any,
        message: str | Callable[[], str],
        delay: int = 450,
        x_offset: int = 12,
        y_offset: int = 14,
        follow: bool = True,
        refresh: int = 0,
        width: int = 420,
        background: str = "#17181c",
        foreground: str = "#f2f2f2",
        border_color: str = "#3c4454",
        font: tuple[str, int] = ("Segoe UI", 9),
    ) -> None:
        self.widget = widget
        self.message = message
        self.delay = delay
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.follow = follow
        self.refresh = refresh
        self.width = width
        self.background = background
        self.foreground = foreground
        self.border_color = border_color
        self.font = font
        self._window: tk.Toplevel | None = None
        self._label: tk.Label | None = None
        self._job: str | None = None
        self._refresh_job: str | None = None
        self._last_pointer = (0, 0)
        self._bindings = [
            ("<Enter>", widget.bind("<Enter>", self._schedule, add="+")),
            ("<Leave>", widget.bind("<Leave>", self._hide, add="+")),
            ("<ButtonPress>", widget.bind("<ButtonPress>", self._hide, add="+")),
        ]
        if follow:
            self._bindings.append(("<Motion>", widget.bind("<Motion>", self._on_motion, add="+")))

    @property
    def host(self) -> tk.Misc:
        return self.widget if hasattr(self.widget, "tk") else self.widget.canvas

    def _message_text(self) -> str:
        value = self.message() if callable(self.message) else self.message
        if isinstance(value, (list, tuple)):
            return "\n".join(str(item) for item in value)
        return str(value)

    def _schedule(self, event: tk.Event | None = None) -> None:
        if event is not None:
            self._last_pointer = (event.x_root, event.y_root)
        self._cancel()
        self._job = self.host.after(self.delay, self._show)

    def _cancel(self) -> None:
        if self._job:
            try:
                self.host.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if self._refresh_job:
            try:
                self.host.after_cancel(self._refresh_job)
            except Exception:
                pass
            self._refresh_job = None

    def _on_motion(self, event: tk.Event) -> None:
        self._last_pointer = (event.x_root, event.y_root)
        if self._window is not None:
            self._position(event.x_root, event.y_root)

    def _show(self) -> None:
        self._job = None
        text = self._message_text()
        if not text:
            return
        if self._window is None:
            window = tk.Toplevel(self.host)
            window.overrideredirect(True)
            try:
                window.attributes("-topmost", True)
            except tk.TclError:
                pass
            frame = tk.Frame(window, background=self.border_color, padx=1, pady=1)
            frame.pack()
            self._label = tk.Label(
                frame,
                text=text,
                justify="left",
                background=self.background,
                foreground=self.foreground,
                padx=9,
                pady=6,
                wraplength=self.width,
                font=self.font,
            )
            self._label.pack()
            self._window = window
        elif self._label is not None:
            self._label.configure(text=text)

        pointer_x, pointer_y = self._last_pointer
        if pointer_x == 0 and pointer_y == 0:
            pointer_x = self.widget.winfo_rootx()
            pointer_y = self.widget.winfo_rooty() + self.widget.winfo_height()
        self._position(pointer_x, pointer_y)
        if self.refresh > 0:
            self._refresh_job = self.host.after(self.refresh, self._refresh_visible)

    def _refresh_visible(self) -> None:
        self._refresh_job = None
        if self._window is None:
            return
        if self._label is not None:
            self._label.configure(text=self._message_text())
        pointer_x, pointer_y = self._last_pointer
        self._position(pointer_x, pointer_y)
        if self.refresh > 0:
            self._refresh_job = self.host.after(self.refresh, self._refresh_visible)

    def _position(self, pointer_x: int, pointer_y: int) -> None:
        if self._window is None:
            return
        self._window.update_idletasks()
        x = pointer_x + self.x_offset
        y = pointer_y + self.y_offset
        width = self._window.winfo_width()
        height = self._window.winfo_height()
        root = self.host.winfo_toplevel()
        left = root.winfo_rootx()
        top = root.winfo_rooty()
        right = left + root.winfo_width()
        bottom = top + root.winfo_height()
        edge = 10
        if x + width > right - edge:
            x = max(left + edge, right - width - edge)
        if x < left + edge:
            x = left + edge
        if y + height > bottom - edge:
            y = pointer_y - height - self.y_offset
        if y < top + edge:
            y = top + edge
        self._window.geometry(f"+{int(x)}+{int(y)}")

    def _hide(self, _: Any = None) -> None:
        self._cancel()
        if self._window is not None:
            self._window.destroy()
            self._window = None
            self._label = None

    def destroy(self) -> None:
        self._hide()
        for sequence, binding_id in self._bindings:
            if binding_id:
                try:
                    self.widget.unbind(sequence, binding_id)
                except Exception:
                    pass
        self._bindings.clear()
