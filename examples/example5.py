"""Image video playback example.

Put your video beside this file as:
    example_vid.mp4

Then run:
    py example5.py

MP4 playback needs an optional decoder:
    cd path/to/project
    py -m pip install -e ".[video]"

or:
    py -m pip install -r requirements-video.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image as PILImage, ImageDraw

# Make this example runnable from any working directory / IDE runner.
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


WIDTH = 1080
HEIGHT = 680


def find_example_video() -> Path | None:
    """Find example_vid.mp4 in the most convenient development locations."""
    candidates = (
        FRAMEWORK_ROOT / "example_vid.mp4",
        FRAMEWORK_ROOT.parent / "example_vid.mp4",
        Path.cwd() / "example_vid.mp4",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def make_scene_background(width: int, height: int) -> PILImage.Image:
    image = PILImage.new("RGBA", (width, height), "#0d1324")
    draw = ImageDraw.Draw(image, "RGBA")

    for y in range(height):
        shade = int(22 + 40 * (y / height))
        draw.line((0, y, width, y), fill=(12, shade, 48, 255))

    draw.ellipse((-160, 90, 420, 670), fill=(55, 210, 190, 95))
    draw.ellipse((760, -180, 1260, 360), fill=(137, 95, 255, 105))
    draw.rounded_rectangle((60, 100, width - 60, height - 70), radius=38, outline=(255, 255, 255, 26), width=2)

    for x in range(0, width, 72):
        draw.line((x, 0, x, height), fill=(255, 255, 255, 14), width=1)
    for y in range(0, height, 72):
        draw.line((0, y, width, y), fill=(255, 255, 255, 14), width=1)

    return image


class VideoExample(Window):
    def __init__(self) -> None:
        super().__init__(
            title="Canvas UI · Image Video",
            width=WIDTH,
            height=HEIGHT,
            locked_width=True,
            locked_height=True,
        )

        self.scene = Frame(self, width=WIDTH, height=HEIGHT, corner_radius=0)
        self.scene.pack(fill="both", expand=True)
        self.scene.canvas.configure(bg="#0d1324")
        Image(
            self.scene,
            image=make_scene_background(WIDTH, HEIGHT),
            width=WIDTH,
            height=HEIGHT,
            x=0,
            y=0,
            anchor="nw",
        ).show()

        Text(
            self.scene,
            text="Image video playback",
            font="Roboto 32 bold",
            fill="#ffffff",
            x=54,
            y=38,
            anchor="nw",
        ).show()
        Text(
            self.scene,
            text='Drop "example_vid.mp4" beside example5.py and run this file.',
            font="Roboto 16",
            fill="#bad7ff",
            x=56,
            y=88,
            anchor="nw",
        ).show()

        self.video: Image | None = None
        self.opacity = 1.0
        self.status = Text(
            self.scene,
            text="",
            font="Roboto 15",
            fill="#8ee6d2",
            x=80,
            y=610,
            anchor="nw",
        )
        self.status.show()

        self._build_video_area()
        self._build_controls()

    def _build_video_area(self) -> None:
        video_path = find_example_video()

        panel = Frame(
            self.scene,
            canvas=self.scene.canvas,
            width=820,
            height=462,
            fg_color="transparent",
        )
        panel.show()
        Image(
            panel,
            x=80,
            y=126,
            width=820,
            height=462,
            anchor="nw",
            fg_color="#020617",
            opacity=0.72,
            border_radius=28,
            border_width=2,
            border_color="#79c8ff",
        ).show()

        if video_path is None:
            Image(
                panel,
                x=110,
                y=156,
                width=760,
                height=402,
                anchor="nw",
                fg_color="#111827",
                border_radius=22,
                border_width=2,
                border_color="#334155",
            ).show()
            Text(
                panel,
                text="No video file found",
                font="Roboto 28 bold",
                fill="#ffffff",
                x=490,
                y=310,
                anchor="center",
            ).show()
            Text(
                panel,
                text=(
                    "Place your file here:\n"
                    "example_vid.mp4\n\n"
                    "Then install video support:\n"
                    'py -m pip install -e ".[video]"'
                ),
                font="Roboto 16",
                fill="#bad7ff",
                justify="center",
                x=490,
                y=375,
                anchor="center",
            ).show()
            self.status.set("Waiting for example_vid.mp4")
            return

        try:
            self.video = Image(
                panel,
                image=video_path,
                x=110,
                y=156,
                width=760,
                height=402,
                anchor="nw",
                opacity=self.opacity,
                border_radius=22,
                border_width=2,
                border_color="#93c5fd",
                video_loop=True,
                video_autoplay=True,
            )
            self.video.show()
        except RuntimeError as exc:
            Image(
                panel,
                x=110,
                y=156,
                width=760,
                height=402,
                anchor="nw",
                fg_color="#111827",
                border_radius=22,
                border_width=2,
                border_color="#7f1d1d",
            ).show()
            Text(
                panel,
                text="Video decoder missing",
                font="Roboto 28 bold",
                fill="#ffffff",
                x=490,
                y=300,
                anchor="center",
            ).show()
            Text(
                panel,
                text=(
                    "Install optional video support:\n"
                    'cd path/to/project\n'
                    'py -m pip install -e ".[video]"\n\n'
                    f"{exc}"
                ),
                font="Roboto 14",
                fill="#fecaca",
                justify="center",
                width=690,
                x=490,
                y=382,
                anchor="center",
            ).show()
            self.status.set("Install the optional video decoder")
            return

        self.status.set(f"Playing {video_path.name}")

    def _build_controls(self) -> None:
        controls = Frame(
            self.scene,
            canvas=self.scene.canvas,
            width=920,
            height=76,
            fg_color="transparent",
        )
        controls.show()
        Image(
            controls,
            x=80,
            y=582,
            width=920,
            height=76,
            anchor="nw",
            fg_color="#101827",
            opacity=0.62,
            border_radius=22,
            border_width=1,
            border_color="#4b8fbd",
        ).show()

        Button(
            controls,
            x=360,
            y=620,
            width=116,
            height=42,
            text="Play",
            font="Roboto 14 bold",
            fg_color="#24507a",
            hover_color="#326b9f",
            select_color="#173b5b",
            border_radius=12,
            command=self.play,
        ).show()
        Button(
            controls,
            x=490,
            y=620,
            width=116,
            height=42,
            text="Pause",
            font="Roboto 14 bold",
            fg_color="#24507a",
            hover_color="#326b9f",
            select_color="#173b5b",
            border_radius=12,
            command=self.pause,
        ).show()
        Button(
            controls,
            x=620,
            y=620,
            width=116,
            height=42,
            text="Restart",
            font="Roboto 14 bold",
            fg_color="#24507a",
            hover_color="#326b9f",
            select_color="#173b5b",
            border_radius=12,
            command=self.restart,
        ).show()
        Button(
            controls,
            x=790,
            y=620,
            width=170,
            height=42,
            text="Toggle opacity",
            font="Roboto 14 bold",
            fg_color="#3f2b6d",
            hover_color="#5b3e9a",
            select_color="#2d1f50",
            border_radius=12,
            command=self.toggle_opacity,
        ).show()

    def play(self) -> None:
        if self.video is not None:
            self.video.play_video()
            self.status.set("Playing")

    def pause(self) -> None:
        if self.video is not None:
            self.video.pause_video()
            self.status.set("Paused")

    def restart(self) -> None:
        if self.video is not None:
            self.video.restart_video()
            self.status.set("Restarted")

    def toggle_opacity(self) -> None:
        if self.video is None:
            return
        self.opacity = 0.45 if self.opacity == 1.0 else 1.0
        self.video.configure(opacity=self.opacity)
        self.status.set(f"Video opacity: {self.opacity:.2f}")


def main() -> None:
    setup("Dark")
    app = VideoExample()
    app.center_window()

    if "--smoke-test" in sys.argv:
        app.open()
        app.update_idletasks()
        app.update()
        assert app.status._is_rendered
        if app.video is not None:
            assert app.video._is_rendered
        app.close()
    else:
        app.open()


if __name__ == "__main__":
    main()
