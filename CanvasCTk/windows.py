from __future__ import annotations

import json
import sys
import tkinter as tk
from collections import deque
from copy import deepcopy
from enum import Enum
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterator

import customtkinter as ctk

from .element import Element


@lru_cache(maxsize=16)
def _cached_normalized_theme(
    path: str,
    modified_ns: int,
    file_size: int,
    platform: str,
) -> dict[str, Any]:
    """Parse and platform-normalize an unchanged CTk theme once."""
    del modified_ns, file_size  # They intentionally participate in the key.
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Theme file must contain a JSON object: {path}")

    platform_key = "macOS" if platform == "darwin" else "Windows" if platform.startswith("win") else "Linux"
    for key in tuple(data):
        section = data[key]
        if isinstance(section, dict) and "macOS" in section:
            data[key] = section[platform_key]

    if "CTkCheckbox" in data:
        data["CTkCheckBox"] = data.pop("CTkCheckbox")
    if "CTkRadiobutton" in data:
        data["CTkRadioButton"] = data.pop("CTkRadiobutton")
    return data


def _normalized_theme(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return _cached_normalized_theme(
        str(path),
        stat.st_mtime_ns,
        stat.st_size,
        sys.platform,
    )


class ThemeMode(str, Enum):
    System = "System"
    Light = "Light"
    Dark = "Dark"


def limit_scaling(
    fit_width: int,
    fit_height: int,
    screen_width: int,
    screen_height: int,
    margin: int = 40,
) -> tuple[int, int, float]:
    """Return a size that fits inside the screen while preserving aspect ratio."""
    available_width = max(1, screen_width - margin)
    available_height = max(1, screen_height - margin)
    scale = min(1.0, available_width / max(1, fit_width), available_height / max(1, fit_height))
    return max(1, int(fit_width * scale)), max(1, int(fit_height * scale)), scale


class WindowBase(Element):
    def _init_window(
        self,
        *,
        title: str,
        resource_root: str | Path | None,
        icon_path: str | Path | None,
        theme_mode: ThemeMode | str,
        width: int,
        height: int,
        resizable: bool,
        locked_width: bool,
        locked_height: bool,
        no_titlebar: bool,
    ) -> None:
        Element.__init__(self)
        self.window_title = title
        self.icon_path = Path(icon_path).expanduser().resolve() if icon_path else None
        self.theme_mode = theme_mode if isinstance(theme_mode, ThemeMode) else ThemeMode(str(theme_mode))
        self.window_width = int(width)
        self.window_height = int(height)
        self.window_resizable = bool(resizable)
        self.locked_width = bool(locked_width)
        self.locked_height = bool(locked_height)
        self.no_titlebar = bool(no_titlebar)
        self.resource_root = Path(resource_root or ".").resolve()
        self.theme_path: Path | None = None
        self._theme_generation = 0
        self._theme_job: dict[str, Any] | None = None
        self.top_levels: list[Toplevel] = []
        self.exists = True

    def apply_config(self) -> None:
        ctk.set_appearance_mode(self.theme_mode.value)
        self.title(self.window_title)
        self.geometry(f"{self.window_width}x{self.window_height}")
        self.resizable(
            self.window_resizable and not self.locked_width,
            self.window_resizable and not self.locked_height,
        )
        if self.no_titlebar:
            self.overrideredirect(True)
        if self.icon_path:
            try:
                self.iconbitmap(str(self.icon_path))
            except Exception:
                pass

    @staticmethod
    def validate_theme(theme: str | Path) -> Path:
        """Validate that a CustomTkinter theme path exists and contains JSON."""
        path = Path(theme).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Theme file not found: {path}")
        _normalized_theme(path)
        return path

    def load_theme(
        self,
        theme: str | Path,
        appearance: str | ThemeMode | None = None,
        recursive: bool = True,
        *,
        incremental: bool | None = None,
        on_complete: Callable[[Path], Any] | None = None,
    ) -> Path:
        """Load a CustomTkinter theme and re-apply framework theme values."""
        path = self.validate_theme(theme)
        self._cancel_theme_job()
        ctk.ThemeManager.theme = deepcopy(_normalized_theme(path))
        ctk.ThemeManager._currently_loaded_theme = str(path)
        self.theme_path = path
        if appearance is not None:
            self.set_appearance(appearance)
        use_incremental = self._theme_should_increment() if incremental is None else bool(incremental)
        if not recursive:
            if use_incremental:
                self._start_theme_job(self, path, on_complete, recursive=False)
            else:
                self._apply_theme_target(self)
                if on_complete is not None:
                    on_complete(path)
            return path

        if use_incremental:
            self._start_theme_job(self, path, on_complete)
        else:
            self._apply_theme_tree_sync(self)
            if on_complete is not None:
                on_complete(path)
        return path

    def reload_theme(
        self,
        recursive: bool = True,
        *,
        incremental: bool | None = None,
        on_complete: Callable[[Path | None], Any] | None = None,
    ) -> Path | None:
        """Reload the last theme passed to ``load_theme``."""
        if self.theme_path is None:
            self._cancel_theme_job()
            use_incremental = self._theme_should_increment() if incremental is None else bool(incremental)
            if not recursive:
                if use_incremental:
                    self._start_theme_job(self, None, on_complete, recursive=False)
                else:
                    self._apply_theme_target(self)
                    if on_complete is not None:
                        on_complete(None)
                return None
            if use_incremental:
                self._start_theme_job(self, None, on_complete)
            else:
                self._apply_theme_tree_sync(self)
                if on_complete is not None:
                    on_complete(None)
            return None
        return self.load_theme(
            self.theme_path,
            recursive=recursive,
            incremental=incremental,
            on_complete=on_complete,
        )

    def apply_theme_tree(self, widget: Any | None = None) -> None:
        """Apply framework theme values to this window, child widgets, and canvas elements."""
        self._cancel_theme_job()
        self._apply_theme_tree_sync(widget or self)

    def _iter_theme_tree(self, widget: Any) -> Iterator[Any]:
        pending = deque([widget])
        visited: set[int] = set()
        visited_canvases: set[int] = set()
        while pending:
            current = pending.popleft()
            identity = id(current)
            if identity in visited:
                continue
            visited.add(identity)

            yield current

            pending.extend(tuple(getattr(current, "elements", {}).values()))
            pending.extend(tuple(getattr(current, "_child_widgets", ())))

            if isinstance(current, tk.Misc):
                try:
                    pending.extend(current.winfo_children())
                except tk.TclError:
                    pass

            canvas_sources = (
                current,
                getattr(current, "canvas", None),
                getattr(current, "_content_canvas", None),
            )
            for source in canvas_sources:
                if source is None:
                    continue
                source_identity = id(source)
                if source_identity in visited_canvases:
                    continue
                refs = getattr(source, "_canvas_ui_item_refs", None)
                if refs is None:
                    continue
                visited_canvases.add(source_identity)
                pending.extend(tuple(refs))

    @staticmethod
    def _apply_theme_target(current: Any) -> None:
        if getattr(current, "_destroyed", False):
            return
        current._canvasctk_theme_applying = True
        try:
            if hasattr(current, "_apply_theme"):
                current._apply_theme(False)
            if hasattr(current, "_update_canvas_color"):
                current._update_canvas_color()
        finally:
            current._canvasctk_theme_applying = False

    def _apply_theme_tree_sync(self, widget: Any) -> None:
        for current in self._iter_theme_tree(widget):
            self._apply_theme_target(current)

    def _theme_should_increment(self) -> bool:
        try:
            return bool(self.winfo_viewable())
        except tk.TclError:
            return False

    def _cancel_theme_job(self) -> None:
        self._theme_generation += 1
        job = self._theme_job
        self._theme_job = None
        if job is None:
            return
        after_id = job.get("after_id")
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass

    def _start_theme_job(
        self,
        widget: Any,
        path: Path | None,
        on_complete: Callable[[Any], Any] | None,
        *,
        recursive: bool = True,
    ) -> None:
        self._theme_generation += 1
        generation = self._theme_generation
        self._theme_job = {
            "generation": generation,
            "iterator": self._iter_theme_tree(widget) if recursive else iter((widget,)),
            "path": path,
            "on_complete": on_complete,
            "after_id": None,
        }
        # An explicitly incremental load must return before applying even a
        # small tree. Startup remains synchronous because callers using the
        # default mode only select this path once the window is viewable.
        self._theme_job["after_id"] = self.after_idle(
            lambda current_generation=generation: self._run_theme_slice(current_generation)
        )

    def _run_theme_slice(self, generation: int) -> None:
        job = self._theme_job
        if job is None or job.get("generation") != generation or generation != self._theme_generation:
            return
        try:
            if not self.winfo_exists():
                self._theme_job = None
                return
        except tk.TclError:
            self._theme_job = None
            return

        job["after_id"] = None
        deadline = perf_counter() + 0.008
        applied = 0
        iterator = job["iterator"]
        while applied == 0 or perf_counter() < deadline:
            try:
                current = next(iterator)
            except StopIteration:
                callback = job.get("on_complete")
                path = job.get("path")
                self._theme_job = None
                if callback is not None and generation == self._theme_generation:
                    callback(path)
                return
            self._apply_theme_target(current)
            applied += 1

        if self._theme_job is job and generation == self._theme_generation:
            job["after_id"] = self.after_idle(
                lambda current_generation=generation: self._run_theme_slice(current_generation)
            )

    def set_appearance(self, appearance: str | ThemeMode) -> None:
        self.theme_mode = appearance if isinstance(appearance, ThemeMode) else ThemeMode(str(appearance))
        ctk.set_appearance_mode(self.theme_mode.value)
        self._update_canvas_color()

    def _create_canvas(self) -> None:
        self.canvas = ctk.CTkCanvas(self, highlightthickness=0)
        self._update_canvas_color()
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._video_drag_last_position: tuple[int, int] | None = None
        self._video_drag_resume_after_id: str | None = None
        self._video_drag_paused: list[Any] = []
        self._video_drag_monitor_stop: Any = None
        self._video_drag_monitor_thread: Any = None
        self._video_drag_monitor_after_id: str | None = None
        self._video_drag_resume_requested = False
        self._video_drag_service_after_id: str | None = None
        self.bind("<Configure>", self._handle_video_drag_pause, add="+")
        if sys.platform == "win32":
            self._video_drag_monitor_after_id = self.after_idle(
                self._start_video_drag_monitor
            )

    def _pause_active_videos_for_drag(self) -> None:
        if self._video_drag_paused:
            return
        for item in tuple(getattr(self.canvas, "_canvas_ui_item_refs", ())):
            if (
                getattr(item, "_is_video", False)
                and getattr(item, "_video_is_playing", False)
                and not getattr(item, "_destroyed", False)
            ):
                # Native move loops can temporarily block Tcl callbacks. Keep
                # this path Python-only so decoding stops immediately without
                # stopping and rebuilding the playback pipeline.
                item._video_decode_pause.set()
                self._video_drag_paused.append(item)

    def _schedule_video_resume_after_drag(self, delay: int = 150) -> None:
        if not self._video_drag_paused:
            return
        if self._video_drag_resume_after_id is not None:
            try:
                self.after_cancel(self._video_drag_resume_after_id)
            except tk.TclError:
                pass
        self._video_drag_resume_after_id = self.after(delay, self._resume_videos_after_drag)

    def _start_video_drag_monitor(self) -> None:
        """Pause decoders when the native window rectangle moves under the mouse."""
        self._video_drag_monitor_after_id = None
        try:
            import ctypes
            import threading
            from ctypes import wintypes

            # Use a private DLL wrapper. Setting ``argtypes`` on
            # ``ctypes.windll.user32`` mutates the shared function objects for
            # the entire process. Applications that define their own RECT
            # structure (such as input.py) then fail with an incompatible
            # LP_RECT argument type after this monitor starts.
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
            user32.GetAncestor.restype = wintypes.HWND
            user32.GetWindowRect.argtypes = (
                wintypes.HWND,
                ctypes.POINTER(wintypes.RECT),
            )
            user32.GetWindowRect.restype = wintypes.BOOL
            user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
            user32.GetAsyncKeyState.restype = ctypes.c_short
            hwnd = user32.GetAncestor(self.winfo_id(), 2) or self.winfo_id()
            stop_event = threading.Event()
            self._video_drag_monitor_stop = stop_event

            def window_rect() -> tuple[int, int, int, int] | None:
                rect = wintypes.RECT()
                if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    return None
                return rect.left, rect.top, rect.right, rect.bottom

            initial_rect = window_rect()
            if initial_rect is None:
                return

            def monitor() -> None:
                previous_rect = initial_rect
                drag_detected = False
                try:
                    while not stop_event.wait(0.03):
                        current_rect = window_rect()
                        if current_rect is None:
                            return
                        left_button_down = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
                        if left_button_down and current_rect != previous_rect:
                            # Only Python flags and threading events are touched;
                            # this monitor never calls Tk.
                            if not drag_detected:
                                self._pause_active_videos_for_drag()
                            drag_detected = True
                        elif drag_detected and not left_button_down:
                            self._video_drag_resume_requested = True
                            drag_detected = False
                        previous_rect = current_rect
                except Exception:
                    # Never forward monitor failures to threading.excepthook.
                    return

            thread = threading.Thread(
                target=monitor,
                name="CanvasCTk-window-drag-monitor",
                daemon=True,
            )
            self._video_drag_monitor_thread = thread
            thread.start()
            self._video_drag_service_after_id = self.after(
                50, self._service_video_drag_monitor
            )
        except Exception:
            self._video_drag_monitor_stop = None
            self._video_drag_monitor_thread = None

    def _service_video_drag_monitor(self) -> None:
        """Handle the monitor's resume request from Tk's main thread."""
        self._video_drag_service_after_id = None
        if not self.exists:
            return
        if self._video_drag_resume_requested:
            self._video_drag_resume_requested = False
            self._resume_videos_after_drag()
            # Windows runs interactive title-bar movement in a native modal
            # loop.  On some Tk builds the final <Configure> notification is
            # swallowed, so application callbacks that reposition companion
            # windows never see the new root position.  Emit one catch-up
            # notification after release. Normal Configure delivery remains
            # harmless because consumers can compare the unchanged position.
            try:
                self.event_generate("<Configure>", when="tail")
            except tk.TclError:
                pass
        try:
            self._video_drag_service_after_id = self.after(
                50, self._service_video_drag_monitor
            )
        except tk.TclError:
            self._video_drag_service_after_id = None

    def _handle_video_drag_pause(self, event: Any = None) -> None:
        """Pause active videos while the native window is being moved."""
        if event is not None and getattr(event, "widget", self) is not self:
            return
        if sys.platform == "win32" and self._video_drag_monitor_thread is not None:
            return
        try:
            position = self.winfo_x(), self.winfo_y()
        except tk.TclError:
            return
        previous_position = self._video_drag_last_position
        self._video_drag_last_position = position
        if previous_position is None or position == previous_position:
            return

        self._pause_active_videos_for_drag()
        self._schedule_video_resume_after_drag()

    def _resume_videos_after_drag(self) -> None:
        self._video_drag_resume_after_id = None
        paused, self._video_drag_paused = self._video_drag_paused, []
        for item in paused:
            if getattr(item, "_destroyed", False) or not getattr(item, "_is_video", False):
                continue
            if (
                getattr(item, "_is_rendered", False)
                and getattr(item, "_video_is_playing", False)
            ):
                item._video_decode_pause.clear()

    def _update_canvas_color(self) -> None:
        canvas = getattr(self, "canvas", None)
        if canvas is None:
            return
        try:
            color = self._apply_appearance_mode(self.cget("fg_color"))
        except Exception:
            theme_key = "CTkToplevel" if isinstance(self, ctk.CTkToplevel) else "CTk"
            color = self._apply_appearance_mode(ctk.ThemeManager.theme[theme_key]["fg_color"])
        if color == "transparent":
            color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTk"]["fg_color"])
        canvas.configure(bg=color)

    def center_window(self) -> None:
        self.update_idletasks()
        width = self.winfo_width() or self.window_width
        height = self.winfo_height() or self.window_height
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        try:
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass

    def fit_to_screen(self, margin: int = 40, center: bool = True) -> tuple[int, int, float]:
        """Shrink the configured window size if it is larger than the screen."""
        width, height, scale = limit_scaling(
            self.window_width,
            self.window_height,
            self.winfo_screenwidth(),
            self.winfo_screenheight(),
            margin=margin,
        )
        self.window_width = width
        self.window_height = height
        self.geometry(f"{width}x{height}")
        if center:
            self.center_window()
        return width, height, scale

    def move(self, x_offset: int = 0, y_offset: int = 0) -> None:
        """Move a borderless window using pointer-relative drag offsets."""
        x = self.winfo_pointerx() - x_offset
        y = self.winfo_pointery() - y_offset
        self.geometry(f"+{x}+{y}")

    def get_resource_path(self, resource_path: str | Path = "") -> Path:
        return self.resource_root / resource_path

    def add_top_level(self, window: "Toplevel") -> None:
        if window not in self.top_levels:
            self.top_levels.append(window)

    def remove_top_level(self, window: "Toplevel") -> None:
        if window in self.top_levels:
            self.top_levels.remove(window)

    def get_top_level(self, locking: bool = False) -> Any:
        candidates = [window for window in self.top_levels if not locking or window.lock_master]
        return candidates[-1] if candidates else self

    def hide(self, hide: bool = True) -> None:
        self.withdraw() if hide else self.deiconify()

    def show(self, show: bool = True) -> None:
        self.deiconify() if show else self.withdraw()

    def is_shown(self) -> bool:
        return bool(self.winfo_exists()) and self.state() == "normal"

    def destroy(self) -> None:
        self.exists = False
        self._cancel_theme_job()
        monitor_after_id = getattr(self, "_video_drag_monitor_after_id", None)
        if monitor_after_id is not None:
            try:
                self.after_cancel(monitor_after_id)
            except tk.TclError:
                pass
            self._video_drag_monitor_after_id = None
        monitor_stop = getattr(self, "_video_drag_monitor_stop", None)
        if monitor_stop is not None:
            monitor_stop.set()
        self._video_drag_monitor_stop = None
        self._video_drag_monitor_thread = None
        service_after_id = getattr(self, "_video_drag_service_after_id", None)
        if service_after_id is not None:
            try:
                self.after_cancel(service_after_id)
            except tk.TclError:
                pass
            self._video_drag_service_after_id = None
        self._video_drag_resume_requested = False
        after_id = getattr(self, "_video_drag_resume_after_id", None)
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
            self._video_drag_resume_after_id = None
        self._video_drag_paused = []
        self._cleanup_canvas_element()
        super().destroy()

    def close(self) -> None:
        self.destroy()


class Window(WindowBase, ctk.CTk):
    def __init__(
        self,
        fg_color: Any = None,
        *,
        title: str = "Window",
        resource_root: str | Path | None = None,
        icon_path: str | Path | None = None,
        theme_mode: ThemeMode | str = ThemeMode.System,
        width: int = 800,
        height: int = 600,
        x: int | None = None,
        y: int | None = None,
        resizable: bool = True,
        locked_width: bool = False,
        locked_height: bool = False,
        no_titlebar: bool = False,
        **kwargs: Any,
    ) -> None:
        ctk.CTk.__init__(self, fg_color=fg_color, **kwargs)
        self._init_window(
            title=title,
            resource_root=resource_root,
            icon_path=icon_path,
            theme_mode=theme_mode,
            width=width,
            height=height,
            resizable=resizable,
            locked_width=locked_width,
            locked_height=locked_height,
            no_titlebar=no_titlebar,
        )
        self.window_x = None if x is None else int(x)
        self.window_y = None if y is None else int(y)
        self._track_theme_defaults("CTk", fg_color=fg_color is None)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.apply_config()
        if self.window_x is not None or self.window_y is not None:
            position_x = 0 if self.window_x is None else self.window_x
            position_y = 0 if self.window_y is None else self.window_y
            self.geometry(
                f"{self.window_width}x{self.window_height}"
                f"{position_x:+d}{position_y:+d}"
            )
        self._create_canvas()
        self.bind_all(
            "<Button-1>",
            lambda event: event.widget.focus_set()
            if hasattr(event.widget, "focus_set")
            else None,
            add="+",
        )

    def open(self) -> None:
        self.deiconify()
        self.lift()
        try:
            # Borderless windows can otherwise open behind the launching IDE
            # on Windows. Brief topmost status presents the app, then restores
            # normal window ordering.
            self.attributes("-topmost", True)
            self.focus_force()
            self.after(150, lambda: self.attributes("-topmost", False))
        except Exception:
            pass
        self.mainloop()

    def minimize(self) -> None:
        self.iconify()


class Toplevel(WindowBase, ctk.CTkToplevel):
    """CustomTkinter-compatible Toplevel with a CanvasCTk drawing surface."""

    def __init__(
        self,
        master: Any = None,
        fg_color: Any = None,
        *args: Any,
        title: str = "Toplevel",
        resource_root: str | Path | None = None,
        icon_path: str | Path | None = None,
        theme_mode: ThemeMode | str = ThemeMode.System,
        width: int = 200,
        height: int = 200,
        x: int | None = None,
        y: int | None = None,
        resizable: bool = True,
        locked_width: bool = False,
        locked_height: bool = False,
        no_titlebar: bool = False,
        lock_master: bool = False,
        **kwargs: Any,
    ) -> None:
        self._canvasctk_intentionally_withdrawn = False
        ctk.CTkToplevel.__init__(
            self,
            master,
            *args,
            fg_color=fg_color,
            **kwargs,
        )
        self._init_window(
            title=title,
            resource_root=resource_root,
            icon_path=icon_path,
            theme_mode=theme_mode,
            width=width,
            height=height,
            resizable=resizable,
            locked_width=locked_width,
            locked_height=locked_height,
            no_titlebar=no_titlebar,
        )
        self.lock_master = bool(lock_master)
        self.window_x = None if x is None else int(x)
        self.window_y = None if y is None else int(y)
        self._canvasctk_owner = master if hasattr(master, "add_top_level") else None
        if self._canvasctk_owner is not None:
            self._canvasctk_owner.add_top_level(self)

        self.title(self.window_title)
        geometry = f"{self.window_width}x{self.window_height}"
        if self.window_x is not None or self.window_y is not None:
            position_x = 0 if self.window_x is None else self.window_x
            position_y = 0 if self.window_y is None else self.window_y
            geometry += f"{position_x:+d}{position_y:+d}"
        self.geometry(geometry)
        self.resizable(
            self.window_resizable and not self.locked_width,
            self.window_resizable and not self.locked_height,
        )
        if self.no_titlebar:
            self.overrideredirect(True)
        if self.icon_path:
            try:
                self.iconbitmap(str(self.icon_path))
            except Exception:
                pass
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._track_theme_defaults("CTkToplevel", fg_color=fg_color is None)
        self.canvas = ctk.CTkCanvas(
            master=self,
            bg=self._apply_appearance_mode(self._fg_color),
            highlightthickness=0,
            bd=0,
        )
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._canvasctk_show_idle_id: str | None = None
        self._canvasctk_show_after_id: str | None = None
        self._canvasctk_show_on_creation()
        self._canvasctk_show_idle_id = self.after_idle(
            self._canvasctk_show_from_idle
        )
        self._canvasctk_show_after_id = self.after(
            20, self._canvasctk_show_delayed
        )

    def _canvasctk_show_from_idle(self) -> None:
        self._canvasctk_show_idle_id = None
        self._canvasctk_show_on_creation()

    def _canvasctk_show_delayed(self) -> None:
        self._canvasctk_show_after_id = None
        self._canvasctk_show_on_creation()

    def _canvasctk_show_on_creation(self) -> None:
        try:
            if not self.winfo_exists():
                return
            if self._canvasctk_intentionally_withdrawn:
                return
            if self.state() == "withdrawn":
                self.deiconify()
            if self.state() in {"normal", "zoomed"}:
                self.lift()
        except tk.TclError:
            pass

    def withdraw(self) -> None:
        self._canvasctk_intentionally_withdrawn = True
        super().withdraw()

    def deiconify(self) -> None:
        self._canvasctk_intentionally_withdrawn = False
        super().deiconify()

    def _revert_withdraw_after_windows_set_titlebar_color(self) -> None:
        """Ignore CTk's delayed title-bar callback after this window is gone."""
        try:
            if not self.winfo_exists():
                return
            super()._revert_withdraw_after_windows_set_titlebar_color()
        except tk.TclError:
            # CTk schedules this callback without retaining its ``after`` ID,
            # so a Toplevel can be destroyed between the existence check and
            # its internal deiconify/state call.
            return

    def configure(self, **kwargs: Any) -> None:
        super().configure(**kwargs)
        if hasattr(self, "canvas"):
            try:
                self.canvas.configure(
                    bg=self._apply_appearance_mode(self._fg_color)
                )
            except tk.TclError:
                pass

    config = configure

    def destroy(self) -> None:
        for attribute in ("_canvasctk_show_idle_id", "_canvasctk_show_after_id"):
            after_id = getattr(self, attribute, None)
            if after_id is not None:
                try:
                    self.after_cancel(after_id)
                except tk.TclError:
                    pass
                setattr(self, attribute, None)
        owner = getattr(self, "_canvasctk_owner", None)
        if owner is not None:
            try:
                owner.remove_top_level(self)
            except (AttributeError, tk.TclError):
                pass
            self._canvasctk_owner = None
        super().destroy()

    def get_resource_path(self, resource_path: str) -> Path:
        return self.resource_root / resource_path
