"""Showcase for every public widget in the Canvas framework.

Run:
    py widgets.py

This is the main widget gallery. ``example.py`` delegates to this file.
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

from PIL import Image as PILImage, ImageDraw

FRAMEWORK_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from CanvasCTk import (
    Button,
    Checkbox,
    Dialog,
    Entry,
    Frame,
    Image,
    Label,
    MessageBox,
    OptionMenu,
    ProgressBar,
    RadioButton,
    ScrollableFrame,
    ScrollableDropdown,
    ScrollableTabview,
    Slider,
    Switch,
    TabView,
    Text,
    Textbox,
    Toplevel,
    Window,
    set_widget_scaling,
    setup,
)


def demo_image(size: int = 96) -> PILImage.Image:
    image = PILImage.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rounded_rectangle((4, 4, size - 4, size - 4), radius=22, fill=(31, 83, 141, 255), outline=(128, 201, 255, 255), width=3)
    draw.polygon(((size // 2, 18), (size - 20, size - 20), (20, size - 20)), fill=(241, 245, 249, 255))
    return image


def checker_background(width: int, height: int) -> PILImage.Image:
    image = PILImage.new("RGBA", (width, height), "#101827")
    draw = ImageDraw.Draw(image, "RGBA")
    for y in range(0, height, 36):
        for x in range(0, width, 36):
            fill = (24, 36, 60, 255) if (x // 36 + y // 36) % 2 else (16, 24, 42, 255)
            draw.rectangle((x, y, x + 36, y + 36), fill=fill)
    draw.ellipse((-120, 80, 260, 460), fill=(46, 196, 182, 90))
    draw.ellipse((430, -120, 820, 240), fill=(122, 92, 255, 95))
    return image


class WidgetShowcase(Window):
    def __init__(self) -> None:
        super().__init__(title="Canvas UI · Widget Showcase", width=1100, height=760)
        self.minsize(960, 650)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = Frame(self, height=76, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        Label(header, text="Canvas UI Framework", font=("Roboto", 28, "bold")).pack(side="left", padx=24, pady=19)
        self.status = Label(header, text="Ready", text_color="#8ee6d2")
        self.status.pack(side="right", padx=24)

        self.tabs = TabView(self, command=self._tab_changed)
        self.tabs.grid(row=1, column=0, padx=18, pady=(8, 18), sticky="nsew")

        self._build_controls(self.tabs.add("Controls"))
        self._build_canvas_items(self.tabs.add("Canvas items"))
        self._build_containers(self.tabs.add("Containers"))
        self._build_windows_dialogs(self.tabs.add("Windows & dialogs"))

    def note(self, message: str) -> None:
        self.status.set(message)

    def _tab_changed(self) -> None:
        self.note(f"Tab: {self.tabs.get()}")

    def _build_controls(self, parent: tk.Misc) -> None:
        parent.grid_columnconfigure((0, 1), weight=1)

        left = Frame(parent)
        right = Frame(parent)
        left.grid(row=0, column=0, padx=(12, 6), pady=12, sticky="nsew")
        right.grid(row=0, column=1, padx=(6, 12), pady=12, sticky="nsew")

        Label(left, text="Input widgets", font=("Roboto", 20, "bold")).pack(anchor="w", padx=20, pady=(20, 12))

        entry = Entry(left, placeholder_text="Entry · FLOAT filter", input_filter="FLOAT")
        entry.pack(fill="x", padx=20, pady=7)
        entry.set("123.45")
        entry.set_tooltip("Right-click for edit menu. Ctrl+Z/Ctrl+Y supported.", delay=250)

        checkbox_var = tk.BooleanVar(value=True)
        Checkbox(
            left,
            text="Checkbox",
            variable=checkbox_var,
            command=lambda: self.note(f"Checkbox: {checkbox_var.get()}"),
        ).pack(anchor="w", padx=20, pady=10)

        radio_var = tk.IntVar(value=1)
        for value, label in enumerate(("RadioButton A", "RadioButton B"), 1):
            RadioButton(
                left,
                text=label,
                variable=radio_var,
                value=value,
                command=lambda: self.note(f"Radio: {radio_var.get()}"),
            ).pack(anchor="w", padx=20, pady=5)

        self.menu = ScrollableDropdown(
            left,
            values={"fast": "Fast", "balanced": "Balanced", "quality": "High quality"},
            command=lambda key: self.note(f"Option key: {key}"),
        )
        self.menu.pack(fill="x", padx=20, pady=12)
        self.menu.set_tooltip("OptionMenu can map internal keys to user labels.", delay=250)

        text_var = tk.StringVar(value="Textbox syncs with a Tk variable.\nRight-click to test the edit menu.")
        textbox = Textbox(left, text_variable=text_var, height=120)
        textbox.pack(fill="x", padx=20, pady=(4, 20))

        Label(right, text="Actions & feedback", font=("Roboto", 20, "bold")).pack(anchor="w", padx=20, pady=(20, 12))
        Label(right, text="Label · canvas-native text label").pack(anchor="w", padx=20, pady=8)

        button = Button(right, text="Button", command=lambda: self.note("Button clicked"), select_color="#1f538d")
        button.pack(fill="x", padx=20, pady=8)
        button.set_tooltip("Tooltips are built in and cursor-clamped.", delay=250, follow=True)

        selected = Button(right, text="Selectable Button", command=lambda: self.note("Selection button clicked"), select_color="#1f538d")
        selected.pack(fill="x", padx=20, pady=8)
        selected.set_selected(True)

        progress = ProgressBar(right)
        progress.set(0.68)
        progress.pack(fill="x", padx=20, pady=18)

        Button(right, text="Open Toplevel", command=self._open_toplevel).pack(fill="x", padx=20, pady=8)
        Button(right, text="Open MessageBox", command=self._open_message_box).pack(fill="x", padx=20, pady=8)
        Button(right, text="Toggle appearance", command=self._toggle_appearance).pack(fill="x", padx=20, pady=(8, 20))

    def _build_canvas_items(self, parent: tk.Misc) -> None:
        frame = Frame(parent, width=860, height=500, fg_color="#111827", corner_radius=12)
        frame.pack(expand=True, fill="both", padx=24, pady=24)
        frame.canvas.configure(bg="#111827")

        Image(frame, image=checker_background(860, 500), width=860, height=500, x=0, y=0, anchor="nw").show()
        Text(frame, text="Text · Image · Button", font="Roboto 24 bold", fill="#ffffff", x=36, y=36, anchor="nw").show()
        Text(
            frame,
            text="Canvas items are drawn on the frame's canvas. Use Image for backgrounds, cards, opacity, borders, and video.",
            font="Roboto 15",
            fill="#bad7ff",
            width=650,
            x=38,
            y=78,
            anchor="nw",
        ).show()

        Image(
            frame,
            image=demo_image(128),
            x=60,
            y=150,
            width=128,
            height=128,
            anchor="nw",
            fg_color="#020617",
            bg_opacity=0.65,
            border_radius=28,
            border_width=2,
            border_color="#8fd3ff",
            padx=14,
            pady=14,
        ).show()
        Text(frame, text="Image with rounded backing and padding", font="Roboto 15", fill="#e5edf5", x=220, y=200, anchor="w").show()

        image_button = Button(
            frame,
            x=260,
            y=350,
            width=360,
            height=92,
            image=demo_image(56),
            size=(56, 56),
            text="Button states",
            fg_color="#24507a",
            hover_color="#326b9f",
            select_color="#7c3aed",
            bg_normal_opacity=0.55,
            bg_hover_opacity=0.85,
            bg_selected_opacity=0.95,
            bg_hover_brightness=1.15,
            button_hover_brightness=1.2,
            border_radius=18,
            command=lambda: self.note("Button clicked"),
        )
        image_button.show()
        image_button.set_tooltip("Normal, hover, selected, and disabled states can each style opacity/brightness.", delay=250)

        disabled = Button(
            frame,
            x=650,
            y=350,
            width=220,
            height=74,
            text="Disabled",
            fg_color="#334155",
            hover_color="#475569",
            select_color="#1e293b",
            bg_disabled_opacity=0.25,
            border_radius=18,
        )
        disabled.show()
        disabled.set_disabled(True)

    def _build_containers(self, parent: tk.Misc) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        self.scroll = ScrollableFrame(parent, height=470, hide_scrollbar=False)
        self.scroll.grid(row=0, column=0, padx=24, pady=24, sticky="nsew")

        Label(self.scroll, text="Container widgets", font=("Roboto", 22, "bold")).pack(anchor="w", padx=18, pady=(18, 10))
        Label(self.scroll, text="Frame · TabView · ScrollableFrame").pack(anchor="w", padx=18, pady=(0, 14))

        for index in range(1, 18):
            card = Frame(self.scroll, height=52)
            card.pack(fill="x", padx=14, pady=5)
            Label(card, text=f"Reusable container row {index:02d}").pack(side="left", padx=14, pady=12)
            bar = ProgressBar(card, width=180)
            bar.set((index % 10) / 10)
            bar.pack(side="right", padx=14)

    def _build_windows_dialogs(self, parent: tk.Misc) -> None:
        parent.grid_columnconfigure(0, weight=1)

        panel = Frame(parent)
        panel.grid(row=0, column=0, padx=24, pady=24, sticky="nsew")
        Label(panel, text="Window/dialog classes", font=("Roboto", 22, "bold")).pack(anchor="w", padx=24, pady=(24, 10))
        Label(
            panel,
            text=(
                "Window is the main root window and now accepts title/width/height directly.\n"
                "Toplevel is a modal/non-modal child window.\n"
                "Dialog and MessageBox provide reusable launcher-style prompts.\n\n"
                "Base classes exported too: Element, ElementBase, Widget, Item."
            ),
            justify="left",
            wraplength=760,
        ).pack(anchor="w", padx=24, pady=8)

        Button(panel, text="Open Toplevel", command=self._open_toplevel).pack(fill="x", padx=24, pady=(16, 8))
        Button(panel, text="Open Dialog with options", command=self._open_dialog).pack(fill="x", padx=24, pady=8)
        Button(panel, text="Fit window to screen", command=lambda: self.note(f"fit_to_screen: {self.fit_to_screen()}")).pack(fill="x", padx=24, pady=8)
        Button(panel, text="Reload theme tree", command=lambda: (self.reload_theme(), self.note("Theme tree re-applied"))).pack(fill="x", padx=24, pady=(8, 24))

    def _open_toplevel(self) -> None:
        dialog = Toplevel(self)
        dialog.title("Toplevel")
        dialog.geometry("440x240")
        dialog.resizable(False, False)
        Label(dialog, text="Standalone Toplevel", font=("Roboto", 22, "bold")).pack(pady=(40, 12))
        Label(dialog, text="Modal behavior is cross-platform.").pack(pady=8)
        Button(dialog, text="Close", command=dialog.destroy).pack(pady=16)

    def _open_message_box(self) -> None:
        response = MessageBox(
            self,
            title="MessageBox",
            message="This is a reusable modal message box.",
            buttons=("Cancel", "OK"),
            width=520,
            height=270,
        ).ask()
        self.note(f"MessageBox response: {response}")

    def _open_dialog(self) -> None:
        response, options = Dialog(
            self,
            title="Dialog",
            message="Dialog can return both a clicked button and checkbox values.",
            buttons=("No", "Yes"),
            checkbox_options=(("Remember", False), ("Use advanced mode", True)),
            width=560,
            height=330,
        ).ask_with_options()
        self.note(f"Dialog response={response!r}, options={options}")

    def _toggle_appearance(self) -> None:
        import customtkinter as ctk

        next_mode = "Light" if ctk.get_appearance_mode() == "Dark" else "Dark"
        self.set_appearance(next_mode)
        self.note(f"Appearance: {next_mode}")


def main() -> None:
    setup("Dark")
    if "--smoke-test" in sys.argv:
        # Main.py uses this scale, so exercise geometry, text requests, and
        # rounded-corner surface coordinates at the application's real value.
        set_widget_scaling(0.8)
    app = WidgetShowcase()
    app.center_window()

    if "--smoke-test" in sys.argv:
        app.update_idletasks()
        app.update()
        assert app.menu._is_rendered
        app.menu._dropdown_callback("quality")
        assert app.menu.get() == "quality"
        app.tabs.set("Containers")
        app.update_idletasks()
        app.scroll.scroll_to(1.0)
        assert app.scroll._content_extent > app.scroll.winfo_height()
        assert app.scroll._scroll_offset > 0

        # Geometry-managed ScrollableFrame children live on its internal
        # content frame. Argument-less grid calls must therefore advance rows
        # there, and delegated grid configuration must affect the same table.
        geometry_scroll = ScrollableFrame(app, width=120, height=70)
        geometry_scroll.place(x=-500, y=-500)
        geometry_first = Label(geometry_scroll, text="first")
        geometry_second = Label(geometry_scroll, text="second")
        geometry_first.grid()
        geometry_second.grid()
        geometry_scroll.grid_columnconfigure(0, weight=1)
        app.update_idletasks()
        assert [geometry_first.grid_info()["row"], geometry_second.grid_info()["row"]] == [0, 1]
        assert geometry_scroll.grid_columnconfigure(0, "weight") == 1

        geometry_pack = ScrollableFrame(app, width=120, height=70)
        geometry_pack.place(x=-700, y=-500)
        pack_first = Label(geometry_pack, text="first")
        pack_second = Label(geometry_pack, text="second")
        pack_first.pack()
        pack_second.pack()

        geometry_place = ScrollableFrame(app, width=120, height=70)
        geometry_place.place(x=-850, y=-500)
        place_default = Label(geometry_place, text="placed")
        place_default.place()
        app.update_idletasks()
        assert pack_first.winfo_y() < pack_second.winfo_y()
        assert place_default.place_info() == {}

        background_parent = Frame(app, width=100, height=60, fg_color="#123456")
        background_parent.place(x=-1000, y=-500)
        background_button = Button(background_parent, text="resolved")
        background_frame = Frame(background_parent, width=20, height=20)
        assert background_button.cget("bg_color") == "#123456"
        assert background_frame.cget("bg_color") == "#123456"

        # A queued scroll-region refresh after a tab switch must not reveal
        # the inactive tab's scrollbar again.
        visibility_tabs = TabView(app, width=160, height=100)
        visibility_tabs.place(x=-500, y=-350)
        first_tab = visibility_tabs.add("first")
        visibility_tabs.add("second")
        hidden_scroll = ScrollableFrame(first_tab, width=100, height=50)
        hidden_scroll.pack()
        app.update_idletasks()
        track_items = hidden_scroll.canvas.find_withtag(
            hidden_scroll._scrollbar._canvas._tag("border_parts")
        )
        assert track_items
        assert hidden_scroll.canvas.itemcget(track_items[0], "fill") == ""
        visibility_tabs.set("second")
        hidden_scroll._update_scrollregion()
        app.update_idletasks()
        assert not hidden_scroll._scrollbar._is_rendered
        assert all(
            hidden_scroll.canvas.itemcget(item, "state") == "hidden"
            for item in hidden_scroll.canvas.find_withtag(hidden_scroll._scrollbar._canvas._owner_root_tag)
        )
        visibility_tabs.set("first")
        app.update_idletasks()
        assert hidden_scroll._scrollbar._is_rendered

        addon_tabs = ScrollableTabview(app, width=260, height=100, scroll_width=180, scroll_height=30)
        addon_tabs.place(x=-1200, y=-350)
        addon_tabs.add_many(tuple(f"Units {index}" for index in range(1, 8)))
        addon_hidden_scroll = ScrollableFrame(addon_tabs.tab("Units 1"), width=100, height=45)
        addon_hidden_scroll.pack()
        for index in range(8):
            Label(addon_hidden_scroll, text=f"row {index}").pack()
        addon_surface = Frame(app, width=120, height=70, fg_color="#234567")
        addon_surface.place(x=-1500, y=-350)
        addon_label = Label(addon_surface, text="Select Stage")
        addon_label.grid(row=0)
        addon_dropdown = ScrollableDropdown(
            addon_surface,
            width=90,
            values=("One", "Two"),
            dynamic_resizing=False,
            fg_color="#345678",
            button_color="#456789",
        )
        addon_dropdown.grid(row=1)
        app.update_idletasks()
        assert not addon_tabs.tab_scrollable_frame.hide_scrollbar
        assert addon_tabs.tab_scrollable_frame._scrollbar._is_rendered
        assert addon_tabs.tab_scrollable_frame._viewport_geometry()[3] == 30
        assert all(
            addon_tabs.tab_scrollable_frame.canvas.itemcget(item, "state") != "hidden"
            for item in addon_tabs.tab_scrollable_frame.canvas.find_withtag(
                addon_tabs.tab_scrollable_frame._scrollbar._canvas._owner_root_tag
            )
        )
        assert addon_hidden_scroll._scrollbar._is_rendered
        addon_hidden_scroll._schedule_scrollregion_update()
        addon_tabs.select_tab("Units 2")
        app.update_idletasks()
        assert not addon_hidden_scroll._scrollbar._is_rendered
        assert all(
            addon_hidden_scroll.canvas.itemcget(item, "state") == "hidden"
            for item in addon_hidden_scroll.canvas.find_withtag(
                addon_hidden_scroll._scrollbar._canvas._owner_root_tag
            )
        )
        addon_tabs.select_tab("Units 1")
        app.update_idletasks()
        assert addon_hidden_scroll._scrollbar._is_rendered
        assert addon_dropdown.cget("bg_color") == "#234567"
        dropdown_items = addon_dropdown.canvas.find_withtag(
            addon_dropdown._canvas._owner_root_tag
        )
        assert dropdown_items[0] == addon_dropdown._background_id
        # CanvasCTk shares the parent's canvas, so a nominally transparent
        # bg_color does not need CTk's opaque per-widget canvas fallback.
        assert addon_dropdown.canvas.itemcget(addon_dropdown._background_id, "fill") == ""
        background_box = tk.Canvas.coords(
            addon_dropdown.canvas,
            addon_dropdown._background_id,
        )
        # Scaled canvas coordinates are floating-point values; compare with a
        # small tolerance to avoid binary representation noise at 0.8 scaling.
        assert abs(
            (background_box[2] - background_box[0]) - addon_dropdown._apply_widget_scaling(90)
        ) < 1e-6
        assert abs(
            (background_box[3] - background_box[1]) - addon_dropdown._apply_widget_scaling(28)
        ) < 1e-6
        assert all(
            addon_dropdown.canvas.itemcget(item, "fill") == "#345678"
            for item in addon_dropdown.canvas.find_withtag(
                addon_dropdown._canvas._tag("inner_parts_left")
            )
        )
        assert all(
            addon_dropdown.canvas.itemcget(item, "fill") == "#456789"
            for item in addon_dropdown.canvas.find_withtag(
                addon_dropdown._canvas._tag("inner_parts_right")
            )
        )
        addon_dropdown.configure(bg_color="#56789a")
        assert addon_dropdown.canvas.itemcget(addon_dropdown._background_id, "fill") == "#56789a"
        addon_dropdown.configure(bg_color="transparent")
        assert addon_dropdown.cget("bg_color") == "#234567"
        assert addon_dropdown.canvas.itemcget(addon_dropdown._background_id, "fill") == ""

        # The native editor must be flattened over the Entry's explicit
        # bg_color, which is the actual layer below its translucent body.
        translucent_entry = Entry(
            addon_surface,
            fg_color="#204080",
            bg_color="#00ff00",
            opacity=0.5,
        )
        translucent_entry.grid()
        assert translucent_entry._editor_color() == "#10a040"
        assert translucent_entry._entry.cget("bg") == translucent_entry._editor_color()
        translucent_entry.destroy()

        # Main.py's Side Tasks section mixes one explicit grid row with
        # argument-less rows and two nested auto-sized frames. Repeated timer
        # text changes must propagate bottom-up without allowing any row to
        # overlap the next one. Unmanaged conditional controls must stay
        # invisible across a parent hide/show cycle.
        side_tasks_frame = Frame(app)
        side_tasks_frame.place(x=-1900, y=-350)
        side_task_rows = []
        heading = Label(side_tasks_frame, text="----------- Macro Settings -----------", font=("Arial", 20))
        heading.grid(row=0)
        side_task_rows.append(heading)
        for text in (
            "Check for wifi",
            "Save settings on exit",
            "Auto Skip Units",
            "Fast Placement",
            "Disable Force End",
        ):
            switch = Switch(side_tasks_frame, text=text, font=("Arial", 20))
            switch.grid()
            side_task_rows.append(switch)
        side_heading = Label(side_tasks_frame, text="--------------- Side Tasks ---------------", font=("Arial", 20))
        side_heading.grid(pady=2)
        side_task_rows.append(side_heading)

        nested_rows = []
        for switch_text in ("Half hourly challenge", "Auto Rifts"):
            nested = Frame(side_tasks_frame)
            nested.grid()
            Switch(nested, text=switch_text, font=("Arial", 20)).grid()
            timer = Label(nested, text="Loading...", font=("Arial", 20))
            timer.grid(padx=2, pady=2)
            nested_rows.append((nested, timer))
            side_task_rows.append(nested)
        bounty = Switch(side_tasks_frame, text="Auto Bounties", font=("Arial", 20))
        bounty.grid()
        side_task_rows.append(bounty)

        forgotten = Switch(side_tasks_frame, text="Conditional side task", font=("Arial", 20))
        forgotten.grid()
        side_tasks_frame._relayout_children()
        assert forgotten.winfo_manager() == "grid"
        assert forgotten._is_rendered
        forgotten_origin = forgotten._winfo_origin()
        forgotten.grid_forget()
        unmanaged_restart = Frame(side_tasks_frame)
        Label(unmanaged_restart, text="Restart Infinite every N/A Mins", font=("Arial", 18)).grid()
        Slider(unmanaged_restart, to=3599, number_of_steps=3599).grid()

        for index, (_, timer) in enumerate(nested_rows):
            timer.configure(text=f"Next event opens in: 00:4{index}:37")
        app.update_idletasks()
        switch_probe = side_task_rows[1]
        switch_bounds = switch_probe.canvas.bbox(switch_probe._switch_canvas._root_tag)
        switch_text_bounds = switch_probe.canvas.bbox(switch_probe._text_id)
        assert switch_bounds is not None and switch_text_bounds is not None
        assert abs(
            (switch_bounds[1] + switch_bounds[3])
            - (switch_text_bounds[1] + switch_text_bounds[3])
        ) <= 1, (switch_bounds, switch_text_bounds)
        side_tasks_frame.hide()
        side_tasks_frame.show()
        app.update_idletasks()
        assert bounty._is_rendered, "managed Side Tasks child did not restore with its parent"
        side_task_grid_rows = [int(widget.grid_info()["row"]) for widget in side_task_rows]
        assert side_task_grid_rows == list(range(len(side_task_rows))), (
            side_task_grid_rows,
            [
                (type(widget).__name__, manager, options.get("row"), widget._layout_manager, widget._layout_options.get("row"))
                for widget, (manager, options) in side_tasks_frame._child_layouts.items()
            ],
        )
        for current, following in zip(side_task_rows, side_task_rows[1:]):
            assert current.winfo_y() + current.winfo_height() <= following.winfo_y()
        assert forgotten.winfo_manager() == ""
        assert not forgotten._is_rendered
        assert unmanaged_restart.winfo_manager() == ""
        assert not unmanaged_restart._is_rendered
        forgotten.grid()
        side_tasks_frame._relayout_children()
        assert forgotten.winfo_manager() == "grid"
        assert forgotten._is_rendered, "forgotten Side Tasks child could not be managed again"
        assert forgotten._winfo_origin() == forgotten_origin
        assert bounty.winfo_y() + bounty.winfo_height() <= forgotten.winfo_y()
        forgotten.grid_forget()
        geometry_scroll.destroy()
        geometry_pack.destroy()
        geometry_place.destroy()
        background_parent.destroy()
        visibility_tabs.destroy()
        addon_tabs.destroy()
        addon_surface.destroy()
        side_tasks_frame.destroy()

        dialog = MessageBox(app, title="Smoke", message="Widget showcase dialog smoke test", buttons=("OK",))
        dialog.open()
        app.update_idletasks()
        app.update()
        dialog.close()
        app.close()
    else:
        app.open()


if __name__ == "__main__":
    main()
