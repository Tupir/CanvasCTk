"""Transparent Frame example using Image backgrounds.

The filename intentionally follows the requested spelling: ``examle2.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image as PILImage, ImageDraw

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


WIDTH = 960
HEIGHT = 600


def make_background(width: int, height: int) -> PILImage.Image:
    """Create a colorful background that makes transparency easy to see."""
    image = PILImage.new("RGBA", (width, height))
    pixels = image.load()

    for y in range(height):
        for x in range(width):
            horizontal = x / width
            vertical = y / height
            pixels[x, y] = (
                int(20 + 34 * horizontal),
                int(35 + 50 * vertical),
                int(74 + 65 * (1 - horizontal)),
                255,
            )

    draw = ImageDraw.Draw(image, "RGBA")
    draw.ellipse((-100, 50, 360, 510), fill=(46, 196, 182, 145))
    draw.ellipse((640, -120, 1080, 320), fill=(122, 92, 255, 155))
    draw.ellipse((500, 390, 850, 740), fill=(255, 95, 145, 120))

    for x in range(30, width, 60):
        draw.line((x, 0, x, height), fill=(255, 255, 255, 18), width=1)
    for y in range(30, height, 60):
        draw.line((0, y, width, y), fill=(255, 255, 255, 18), width=1)

    return image


class TransparentFrameExample(Window):
    def __init__(self) -> None:
        super().__init__(
            title="Canvas UI · Transparent Frame",
            width=WIDTH,
            height=HEIGHT,
            locked_width=True,
            locked_height=True,
        )

        # The scene owns the visible canvas and its full-window background.
        scene = Frame(self, width=WIDTH, height=HEIGHT, corner_radius=0)
        scene.pack(fill="both", expand=True)
        scene.canvas.configure(bg="#14234a")
        Image(
            scene,
            image=make_background(WIDTH, HEIGHT),
            width=WIDTH,
            height=HEIGHT,
            x=0,
            y=0,
            anchor="nw",
        ).show()

        # Sharing the scene canvas is the important part. The glass frame is a
        # logical Frame, while its translucent background is composited on
        # the already-visible canvas.
        glass = Frame(
            scene,
            canvas=scene.canvas,
            width=780,
            height=420,
            fg_color="transparent",
        )
        glass.show()
        Image(
            glass,
            width=780,
            height=420,
            x=135,
            y=150,
            anchor="w",
            fg_color="#ff0000fd",
            opacity=0.3,
            border_radius=28,
            border_width=2,
            border_color="#ff0000",
        ).show()

        Text(
            glass,
            text="Transparent Frame",
            font="Roboto 30 bold",
            fill="#ffffff",
            anchor="w",
        ).show()
        
        Text(
            glass,
            text="Created with Image(opacity=0.72)",
            font="Roboto 16",
            fill="#b9dff7",
            x=135,
            y=194,
            anchor="w",
        ).show()
        Text(
            glass,
            text=(
                "The circles, gradient, and grid remain visible through this panel.\n"
                "Because both frames share one canvas, PIL alpha is preserved."
            ),
            font="Roboto 17",
            fill="#e5edf5",
            justify="left",
            x=135,
            y=265,
            anchor="w",
        ).show()

        self.status = Text(
            glass,
            text="Ready",
            font="Roboto 15",
            fill="#8ee6d2",
            x=135,
            y=440,
            anchor="w",
        )
        self.status.show()

        Button(
            glass,
            x=690,
            y=430,
            width=260,
            height=62,
            text="Test transparent card",
            font="Roboto 15 bold",
            fg_color="#24507a",
            hover_color="#326b9f",
            select_color="#173b5b",
            border_radius=16,
            command=lambda: self.status.set("Button clicked — transparency stays intact"),
        ).show()


def main() -> None:
    setup("Dark")
    app = TransparentFrameExample()
    app.center_window()

    if "--smoke-test" in sys.argv:
        app.open()
        app.update_idletasks()
        app.update()
        assert app.status._is_rendered
        app.close()
    else:
        app.open()


if __name__ == "__main__":
    main()
