from __future__ import annotations

from typing import Any

from ..containers import Frame, ScrollableFrame
from ..widgets.SegmentedButton import SegmentedButton


class ScrollableTabview(Frame):
    """CanvasCTk port of ``CTKAddons.ScrollableTabview``."""

    def __init__(
        self,
        master: Any,
        width: int = 500,
        height: int = 400,
        scroll_width: int = 200,
        scroll_height: int = 40,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, width=width, height=height, **kwargs)
        self._tab_strip_layout_pending = False
        self._tab_leading_padding = 0
        self._tab_total_width = -1
        self._tab_strip_signature: tuple[Any, ...] | None = None
        self._tab_offsets: dict[str, tuple[int, int]] = {}

        self.tab_scrollable_frame = ScrollableFrame(
            self,
            orientation="horizontal",
            width=scroll_width,
            height=scroll_height,
            # ``scroll_height`` remains the clipped tab-button viewport height;
            # ScrollableFrame adds its horizontal scrollbar below the viewport.
            hide_scrollbar=False,
        )
        self.tab_scrollable_frame.pack(padx=0, pady=0)

        self.segmented_button = SegmentedButton(
            self.tab_scrollable_frame,
            values=[],
            command=self._show_tab,
        )
        self.segmented_button.pack()
        self._bind_tab_strip_scrolling()
        self.tab_scrollable_frame._content_canvas.bind(
            "<Configure>",
            self._schedule_tab_strip_layout,
            add="+",
        )

        self.content_frame = Frame(self)
        self.content_frame.pack(fill="both", expand=True)

        self.tabs: dict[str, Frame] = {}
        self.current_tab: str | None = None

    def _bind_tab_strip_scrolling(self) -> None:
        canvas = self.tab_scrollable_frame._content_canvas
        # Canvas item bindings reject MouseWheel on Tk, so own the nested
        # viewport's widget-level bindings instead. Returning "break" from
        # the callback prevents a second class/all binding from scrolling it.
        canvas.bind("<MouseWheel>", self._on_mousewheel)
        canvas.bind("<Shift-MouseWheel>", self._on_mousewheel)
        canvas.bind("<Button-4>", lambda event: self._on_mousewheel(event, -120))
        canvas.bind("<Button-5>", lambda event: self._on_mousewheel(event, 120))

    def _schedule_tab_strip_layout(self, _event: Any = None) -> None:
        if self._tab_strip_layout_pending:
            return
        self._tab_strip_layout_pending = True
        self.after_idle(self._flush_tab_strip_layout)

    def _flush_tab_strip_layout(self) -> None:
        self._tab_strip_layout_pending = False
        if not self._destroyed and self.winfo_exists():
            self._layout_tab_strip()

    def _segment_widths(self) -> list[int]:
        if not self.tabs:
            return []
        return self.segmented_button._segment_widths()

    def _layout_tab_strip(self) -> None:
        strip = self.tab_scrollable_frame
        _, _, viewport_width, _ = strip._viewport_geometry()
        scaling = float(strip._apply_widget_scaling(1.0))
        signature = (
            viewport_width,
            self.segmented_button._segment_metrics_revision,
            scaling,
        )
        if signature == self._tab_strip_signature:
            return
        self._segment_widths()
        total_width = self.segmented_button._segment_total_width()
        # Center short tab strips inside the viewport. Overflowing strips start
        # at the leading edge so their full range remains scrollable.
        leading_padding = max(0, int((viewport_width - total_width) / 2))
        self._tab_strip_signature = signature
        content_geometry_changed = total_width != self._tab_total_width
        self._tab_total_width = total_width

        self._tab_offsets = {}
        for name in self.tabs:
            bounds = self.segmented_button._segment_bounds(name)
            if bounds is not None:
                self._tab_offsets[name] = (
                    leading_padding + bounds[0],
                    leading_padding + bounds[1],
                )

        if leading_padding != self._tab_leading_padding:
            content_geometry_changed = True
            self._tab_leading_padding = leading_padding
            self.segmented_button.pack_configure(
                side="left",
                anchor="w",
                padx=(leading_padding, 0),
            )

        # Flush the logical content size before changing the view. Without
        # this, add(..., scroll_to_end=True) can run against the previous
        # scrollregion and appear to do nothing.
        if content_geometry_changed:
            strip._content._relayout_children()
        strip._update_scrollregion()
        increment = max(1, int(round(strip._apply_widget_scaling(24))))
        strip._content_canvas.configure(xscrollincrement=increment)
        if total_width <= viewport_width:
            strip._content_canvas.xview_moveto(0)

    def _ensure_tab_visible(self, name: str) -> None:
        if name not in self.tabs:
            return
        self._layout_tab_strip()
        bounds = self._tab_offsets.get(name)
        if bounds is None:
            return
        logical_start, logical_end = bounds
        strip = self.tab_scrollable_frame
        canvas = strip._content_canvas
        scale = strip._apply_widget_scaling
        content_width = max(1.0, scale(max(strip._content_extent, logical_end)))
        viewport_width = float(canvas.winfo_width())
        if viewport_width <= 1:
            viewport_width = float(canvas.cget("width"))
        view_left = canvas.xview()[0] * content_width
        target_left = view_left
        start = scale(logical_start)
        end = scale(logical_end)
        if start < view_left:
            target_left = start
        elif end > view_left + viewport_width:
            target_left = end - viewport_width
        max_left = max(0.0, content_width - viewport_width)
        target_left = min(max(0.0, target_left), max_left)
        canvas.xview_moveto(target_left / content_width)

    def add(self, name: str, scroll_to_end: bool = False) -> Frame:
        if name in self.tabs:
            return self.tabs[name]

        first_tab = not self.tabs
        values = [*self.tabs, name]
        self.segmented_button.configure(values=values)

        tab_frame = Frame(self.content_frame)
        tab_frame.hide()
        self.tabs[name] = tab_frame

        if first_tab:
            self.segmented_button.set(name)
            self._show_tab(name)
        if scroll_to_end:
            self._scroll(1.0)
        else:
            self._schedule_tab_strip_layout()
        return tab_frame

    def add_many(self, names: list[str] | tuple[str, ...], scroll_to_end: bool = False) -> list[Frame]:
        """Create multiple tabs while redrawing the segmented control once."""
        created: list[Frame] = []
        first_name: str | None = None
        for name in names:
            if name in self.tabs:
                created.append(self.tabs[name])
                continue
            if first_name is None and not self.tabs:
                first_name = name
            tab_frame = Frame(self.content_frame)
            tab_frame.hide()
            self.tabs[name] = tab_frame
            created.append(tab_frame)
        self.segmented_button.configure(values=list(self.tabs))
        if first_name is not None:
            self.segmented_button.set(first_name)
            self._show_tab(first_name)
        if scroll_to_end:
            self._scroll(1.0)
        else:
            self._schedule_tab_strip_layout()
        return created

    def tab(self, name: str) -> Frame | None:
        return self.tabs.get(name)

    def delete(self, name: str) -> None:
        if name not in self.tabs:
            return

        self.segmented_button.delete(name)
        removed_tab = self.tabs.pop(name)
        removed_tab.destroy()

        if self.current_tab == name:
            if self.tabs:
                last_tab = next(reversed(self.tabs))
                self.segmented_button.set(last_tab)
                self._show_tab(last_tab)
            else:
                self.current_tab = None
        self._scroll(1.0)

    def select_tab(self, name: str) -> None:
        if name not in self.tabs:
            raise ValueError(f"Unknown tab: {name}")
        self.segmented_button.set(name)
        self._show_tab(name)

    def _show_tab(self, name: str) -> None:
        if name not in self.tabs:
            return
        if self.current_tab == name:
            return

        old_frame = self.tabs.get(self.current_tab) if self.current_tab is not None else None
        selected_frame = self.tabs[name]
        if old_frame is not None:
            if old_frame.winfo_manager() == "pack":
                old_frame.pack_forget()
            elif old_frame._is_rendered:
                old_frame.hide()

        if selected_frame.winfo_manager() != "pack":
            selected_frame.pack(fill="both", expand=True)
            # Keep the new tab hidden only until its real content allocation
            # is known. Waiting for the normal idle layout exposes it briefly
            # at the shared canvas origin during rapid tab switches.
            self.content_frame._relayout_children()
        elif not selected_frame._is_rendered:
            selected_frame.show()
        self.current_tab = name
        self._ensure_tab_visible(name)

    def _on_mousewheel(self, event: Any, delta: int | None = None) -> str | None:
        wheel_delta = int(delta if delta is not None else getattr(event, "delta", 0))
        if not wheel_delta:
            return None
        steps = int(-wheel_delta / 120)
        if not steps:
            steps = -1 if wheel_delta > 0 else 1
        self.tab_scrollable_frame._content_canvas.xview_scroll(steps, "units")
        return "break"

    def _scroll(self, xview: float) -> None:
        self._layout_tab_strip()
        self.tab_scrollable_frame.scroll_to(xview)


__all__ = ["ScrollableTabview"]
