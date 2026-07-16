"""Visual replica of a launcher-style main window.

This example intentionally contains no launcher, updater, settings, or network
logic. It uses the original repository's Default theme assets to test the
standalone widgets, including canvas-widget ``grid`` and ``pack``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from PIL import Image as PILImage

# Some IDE runners use runpy without adding this file's directory to
# sys.path. Make the standalone example runnable from any working directory.
FRAMEWORK_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from CanvasCTk import (
    Frame,
    Image,
    Button,
    Text,
    Window,
    setup,
)


WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
REPOSITORY_ROOT = PROJECT_ROOT
LAUNCHER_ASSETS = REPOSITORY_ROOT / "Themes" / "Default" / "MainWindow" / "LauncherFrame"
TOP_BAR_ASSETS = LAUNCHER_ASSETS / "TopBarFrame"
BOTTOM_BAR_ASSETS = LAUNCHER_ASSETS / "BottomBarFrame"


def optional_asset(path: Path, color: str = "#182235") -> Path | PILImage.Image:
    if path.exists():
        return path
    return PILImage.new("RGBA", (8, 8), color)


def asset(name: str) -> Path | PILImage.Image:
    return optional_asset(LAUNCHER_ASSETS / name)


def top_asset(name: str) -> Path | PILImage.Image:
    return optional_asset(TOP_BAR_ASSETS / name, "#111827")


def bottom_asset(name: str) -> Path | PILImage.Image:
    return optional_asset(BOTTOM_BAR_ASSETS / name, "#0b1220")


class MainWindowReplica(Window):
    IMPORTERS = ("WWMI", "ZZMI", "EFMI", "SRMI", "GIMI", "HIMI")

    def __init__(self) -> None:
        super().__init__(
            title="Canvas Launcher",
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            locked_width=True,
            locked_height=True,
            no_titlebar=True,
            icon_path=REPOSITORY_ROOT / "Themes" / "Default" / "window-icon.ico",
        )

        self.scene = Frame(
            self,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            corner_radius=0,
            fg_color="#05080d",
        )
        self.scene.pack(fill="both", expand=True)
        self.scene.canvas.configure(bg="#05080d")

        background_path = asset("background-image-wwmi.webp")
        self._background_source = (
            PILImage.open(background_path).convert("RGBA")
            if isinstance(background_path, Path)
            else background_path.copy()
        )
        self._scaled_background = self._background_source.resize(
            (WINDOW_WIDTH, WINDOW_HEIGHT), PILImage.Resampling.LANCZOS
        )
        Image(
            self.scene,
            image=self._scaled_background,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            x=0,
            y=0,
            anchor="nw",
        ).show()

        self.status = "HOME"
        self._build_top_bar()
        self._build_bottom_bar()
        self._build_game_selector()

    def _button(
        self,
        *,
        x: int,
        image: Path,
        command: Callable[[], None],
        width: int = 42,
        height: int = 42,
        background: Path | None = None,
        background_size: int = 54,
        tooltip: str = "",
        **style_kwargs,
    ) -> Button:
        if background is not None:
            defaults = {
                "bg_normal_opacity": 0,
                "bg_hover_opacity": 0.4,
                "bg_selected_opacity": 0.6,
                "button_hover_opacity": 1,
                "button_selected_opacity": 1,
            }
            defaults.update(style_kwargs)
            style_kwargs = defaults
        button = Button(
            self.scene,
            x=x,
            y=40,
            width=background_size,
            height=background_size,
            size=(width, height),
            image=image,
            fg_color=None,
            hover_color="#334052",
            select_color="#53647c",
            command=command,
            **style_kwargs,
        )
        button.show()
        if tooltip:
            button.set_tooltip(tooltip, delay=250)
        return button

    def _build_top_bar(self) -> None:
        top_bar = Image(
            self.scene,
            image=top_asset("background-image.png"),
            width=WINDOW_WIDTH,
            height=80,
            x=0,
            y=0,
            anchor="nw",
            opacity=0.65,
        )
        top_bar.show()

        drag = {"x": 0, "y": 0}

        def remember_pointer(event) -> None:
            drag["x"], drag["y"] = event.x, event.y

        def move_window(_event) -> None:
            self.move(drag["x"], drag["y"])

        top_bar.bind("<Button-1>", remember_pointer)
        top_bar.bind("<B1-Motion>", move_window)

        for index, importer in enumerate(self.IMPORTERS):
            button = self._button(
                x=40 + index * 80,
                image=top_asset(f"button-select-game-{importer.lower()}.png"),
                background=top_asset("button-select-game-background.png"),
                background_size=60,
                width=48,
                height=48,
                tooltip=f"{importer} Model Importer",
                command=lambda selected=importer: self._set_status(f"Selected {selected}"),
            )

        home_button = self._button(
            x=40 + len(self.IMPORTERS) * 80,
            image=top_asset("button-select-game-wwmi.png"),
            background=top_asset("button-select-game-background.png"),
            background_size=60,
            width=38,
            height=38,
            tooltip="Manage Model Importers",
            command=lambda: self._set_status("Model importer manager"),
        )
        home_button.set_selected(True)

        self._button(
            x=860,
            image=top_asset("button-resource-discord.png"),
            background=top_asset("button-resource-background.png"),
            tooltip="AGMG Modding Community Discord",
            command=lambda: self._set_status("Discord button works"),
        )
        self._button(
            x=930,
            image=top_asset("button-resource-github.png"),
            background=top_asset("button-resource-background.png"),
            tooltip="Project GitHub",
            command=lambda: self._set_status("GitHub button works"),
        )
        self._button(
            x=1120,
            image=top_asset("button-system-settings.png"),
            background=top_asset("button-system-background.png"),
            width=36,
            height=36,
            background_size=48,
            tooltip="Open Settings",
            command=lambda: self._set_status("Settings button works"),
        )
        self._button(
            x=1180,
            image=top_asset("button-system-minimize.png"),
            background=top_asset("button-system-background.png"),
            width=32,
            height=32,
            background_size=48,
            tooltip="Minimize",
            command=self.minimize,
        )
        self._button(
            x=1240,
            image=top_asset("button-system-close.png"),
            background=top_asset("button-system-background.png"),
            width=32,
            height=32,
            background_size=48,
            tooltip="Close",
            command=self.close,
        )

    def _build_game_selector(self) -> None:
        Text(
            self.scene,
            x=32,
            y=505,
            text="Select Games To Mod:",
            font=("Microsoft YaHei", 24, "bold"),
            fill="white",
            activefill="white",
            anchor="nw",
        ).show()

        # The original centers are x=125+index*206 and y=600. This cropped
        # strip produces those same centers while exercising canvas .grid().
        strip_x, strip_y = 23, 543
        strip_width, strip_height = 1234, 115
        background_crop = self._scaled_background.crop(
            (strip_x, strip_y, strip_x + strip_width, strip_y + strip_height)
        )
        tile_strip = Frame(
            self.scene,
            width=strip_width,
            height=strip_height,
            corner_radius=0,
            fg_color="#05080d",
        )
        tile_strip.place(x=strip_x, y=strip_y)
        tile_strip.canvas.configure(bg="#05080d")
        Image(
            tile_strip,
            image=background_crop,
            width=strip_width,
            height=strip_height,
            x=0,
            y=0,
            anchor="nw",
        ).show()

        for column, importer in enumerate(self.IMPORTERS):
            tile = Button(
                tile_strip,
                width=180,
                height=100,
                size=(184, 102),
                image=asset(f"game-tile-{importer.lower()}.png"),
                fg_color=None,
                hover_color="#17263a",
                select_color="#1f538d",
                command=lambda selected=importer: self._set_status(f"{selected} tile clicked"),
            )
            tile.grid(row=0, column=column, padx=10, pady=6)
            tile.set_tooltip(f"Enable or disable {importer}", delay=250)

    def _build_bottom_bar(self) -> None:
        Image(
            self.scene,
            image=bottom_asset("background-image.png"),
            width=WINDOW_WIDTH,
            height=240,
            x=0,
            y=500,
            anchor="nw",
            opacity=0.75,
        ).show()

        # Canvas widgets now support pack as well as absolute placement.
        self.version_text = Text(
            self.scene,
            text="LAUNCHER 2.2.1",
            font=("Consolas", 16),
            fill="#999999",
            activefill="white",
            anchor="nw",
        )
        self.version_text.pack(side="bottom", anchor="w", padx=20, pady=23)

    def _set_status(self, message: str) -> None:
        self.status = message
        self.version_text.set(message.upper())


def main() -> None:
    setup("Dark")
    app = MainWindowReplica()
    app.center_window()

    if "--smoke-test" in sys.argv:
        app.open()
        app.update_idletasks()
        app.update()
        assert app.version_text._is_rendered
        app.close()
    else:
        app.open()


if __name__ == "__main__":
    main()
