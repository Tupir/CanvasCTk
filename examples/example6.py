"""Launcher-style extras example.

Shows the reusable pieces ported from the original launcher recommendations:
    - Button per-state opacity / brightness
    - improved cursor-following tooltip
    - Entry / Textbox context menus and undo helpers
    - MessageBox modal dialog
    - appearance/theme reload helpers
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import tkinter as tk

# Make this example runnable from any working directory / IDE runner.
FRAMEWORK_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from CanvasCTk import (
    Button,
    Entry,
    Frame,
    Label,
    MessageBox,
    Text,
    Textbox,
    Window,
    setup,
)


class ExtrasExample(Window):
    def __init__(self) -> None:
        super().__init__(title="Canvas UI · Launcher Extras", width=980, height=640)
        self.minsize(860, 580)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = Frame(self, height=78, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        Label(header, text="Launcher-style extras", font=("Roboto", 28, "bold")).pack(side="left", padx=24, pady=20)
        self.status = Label(header, text="Ready", text_color="#8ee6d2")
        self.status.pack(side="right", padx=24)

        main = Frame(self)
        main.grid(row=1, column=0, padx=22, pady=22, sticky="nsew")
        main.grid_columnconfigure((0, 1), weight=1)
        main.grid_rowconfigure(0, weight=1)

        self._build_canvas_buttons(main)
        self._build_inputs(main)

    def note(self, message: str) -> None:
        self.status.set(message)

    def _build_canvas_buttons(self, parent: Frame) -> None:
        panel = Frame(parent, width=430, height=440, fg_color="#111827", corner_radius=18)
        panel.grid(row=0, column=0, padx=(18, 9), pady=18, sticky="nsew")
        panel.canvas.configure(bg="#111827")

        Text(
            panel,
            text="Button states",
            font="Roboto 24 bold",
            fill="#ffffff",
            x=28,
            y=30,
            anchor="nw",
        ).show()
        Text(
            panel,
            text="Normal, hover, selected, and disabled can each use different opacity and brightness.",
            font="Roboto 14",
            fill="#bad7ff",
            width=350,
            x=30,
            y=72,
            anchor="nw",
        ).show()

        selected_button = Button(
            panel,
            x=210,
            y=170,
            width=300,
            height=76,
            text="Selected glass button",
            font="Roboto 15 bold",
            fg_color="#24507a",
            hover_color="#326b9f",
            select_color="#7c3aed",
            bg_normal_opacity=0.45,
            bg_hover_opacity=0.82,
            bg_selected_opacity=0.95,
            bg_disabled_opacity=0.22,
            bg_normal_brightness=0.9,
            bg_hover_brightness=1.15,
            bg_selected_brightness=1.25,
            border_radius=18,
            command=lambda: self.note("Selected-style image button clicked"),
        )
        selected_button.show()
        selected_button.set_selected(True)
        selected_button.set_tooltip(lambda: f"Live tooltip time: {time.strftime('%H:%M:%S')}", delay=250, refresh=500)

        disabled_button = Button(
            panel,
            x=210,
            y=270,
            width=300,
            height=76,
            text="Disabled state",
            font="Roboto 15 bold",
            fg_color="#24507a",
            hover_color="#326b9f",
            select_color="#173b5b",
            bg_disabled_opacity=0.18,
            button_disabled_opacity=0.35,
            border_radius=18,
        )
        disabled_button.show()
        disabled_button.set_disabled(True)
        disabled_button.set_tooltip("Disabled buttons can still show help text.", delay=250)

        Button(
            panel,
            x=210,
            y=365,
            width=300,
            height=58,
            text="Show MessageBox",
            font="Roboto 14 bold",
            fg_color="#1f5f57",
            hover_color="#26796f",
            select_color="#184944",
            border_radius=16,
            command=self.open_dialog,
        ).show()

    def _build_inputs(self, parent: Frame) -> None:
        panel = Frame(parent, fg_color="#111827", corner_radius=18)
        panel.grid(row=0, column=1, padx=(9, 18), pady=18, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)

        Label(panel, text="Input polish", font=("Roboto", 24, "bold")).grid(row=0, column=0, padx=24, pady=(24, 8), sticky="w")
        Label(
            panel,
            text="Right-click the entry/textbox for Cut, Copy, Paste, Undo, Redo, and Select all.",
            wraplength=360,
            justify="left",
            text_color="#bad7ff",
        ).grid(row=1, column=0, padx=24, pady=(0, 16), sticky="w")

        entry = Entry(panel, placeholder_text="Entry with right-click menu", input_filter="FLOAT")
        entry.grid(row=2, column=0, padx=24, pady=8, sticky="ew")
        entry.set("123.45")
        entry.set_tooltip("This entry uses the FLOAT input filter.", delay=250)

        text_var = tk.StringVar(value="Try typing, undoing, pasting, and right-clicking here.")
        textbox = Textbox(panel, text_variable=text_var, height=150)
        textbox.grid(row=3, column=0, padx=24, pady=12, sticky="ew")

        Button(panel, text="Toggle appearance", command=self.toggle_appearance).grid(
            row=4, column=0, padx=24, pady=(12, 8), sticky="ew"
        )
        Button(panel, text="Re-apply current theme", command=lambda: (self.reload_theme(), self.note("Theme re-applied"))).grid(
            row=5, column=0, padx=24, pady=(8, 24), sticky="ew"
        )

    def open_dialog(self) -> None:
        dialog = MessageBox(
            self,
            title="Reusable MessageBox",
            message="This is a standalone modal dialog extracted from the launcher-style Canvas workflow.",
            buttons=("Cancel", "OK"),
            checkbox_options=(("Remember my choice", False), ("Show advanced option", True)),
            width=560,
            height=330,
        )
        response, options = dialog.ask_with_options()
        self.note(f"Dialog response={response!r}, options={options}")

    def toggle_appearance(self) -> None:
        import customtkinter as ctk

        next_mode = "Light" if ctk.get_appearance_mode() == "Dark" else "Dark"
        self.set_appearance(next_mode)
        self.note(f"Appearance: {next_mode}")


def main() -> None:
    setup("Dark")
    app = ExtrasExample()
    app.center_window()

    if "--smoke-test" in sys.argv:
        app.open()
        app.update_idletasks()
        app.update()
        assert any(
            app.canvas.itemcget(item_id, "state") != "hidden"
            for item_id in app.canvas.find_all()
        )
        dialog = MessageBox(app, title="Smoke", message="Dialog smoke test", buttons=("OK",))
        dialog.open()
        app.update_idletasks()
        app.update()
        dialog.close()
        app.close()
    else:
        app.open()


if __name__ == "__main__":
    main()
