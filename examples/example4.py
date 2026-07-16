"""Exact transparency / opacity patterns for the standalone Canvas UI framework.

Run:
    py example4.py

The important idea:
    Tk/CustomTkinter widgets do not have true per-widget alpha transparency.
    This framework gets real opacity by drawing RGBA images on one shared canvas.

Use these two patterns:
    1. Transparent frame/card:
       frame = Frame(scene, canvas=scene.canvas, fg_color="transparent")
       Image(frame, fg_color="#101827", opacity=0.45, ...)

    2. Transparent image/overlay:
       Image(scene, fg_color="#000000", opacity=0.25, ...)
       Image(scene, image=my_pil_image, opacity=0.50, ...)
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


WIDTH = 1100
HEIGHT = 680


def make_checker_background(width: int, height: int) -> PILImage.Image:
    """Busy background so transparent panels are obvious."""
    image = PILImage.new("RGBA", (width, height), "#101827")
    draw = ImageDraw.Draw(image, "RGBA")

    tile = 40
    for y in range(0, height, tile):
        for x in range(0, width, tile):
            odd = (x // tile + y // tile) % 2
            color = (28, 41, 68, 255) if odd else (17, 27, 48, 255)
            draw.rectangle((x, y, x + tile, y + tile), fill=color)

    # Big soft shapes underneath the cards.
    draw.ellipse((-100, 80, 420, 600), fill=(39, 211, 184, 115))
    draw.ellipse((720, -120, 1230, 390), fill=(128, 92, 255, 120))
    draw.ellipse((500, 390, 980, 850), fill=(255, 90, 150, 100))

    for x in range(0, width, 80):
        draw.line((x, 0, x, height), fill=(255, 255, 255, 18), width=1)
    for y in range(0, height, 80):
        draw.line((0, y, width, y), fill=(255, 255, 255, 18), width=1)

    return image


def make_icon_image(size: int = 180) -> PILImage.Image:
    """Transparent PNG-like image generated in memory."""
    image = PILImage.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rounded_rectangle((16, 16, size - 16, size - 16), radius=34, fill=(98, 179, 255, 255))
    draw.ellipse((48, 42, size - 48, size - 54), fill=(255, 255, 255, 210))
    draw.polygon(
        [(size // 2, 58), (size - 54, size - 54), (54, size - 54)],
        fill=(24, 38, 68, 235),
    )
    return image


class OpacityExample(Window):
    def __init__(self) -> None:
        super().__init__(
            title="Canvas UI · Transparency / Opacity",
            width=WIDTH,
            height=HEIGHT,
            locked_width=True,
            locked_height=True,
        )

        self.scene = Frame(self, width=WIDTH, height=HEIGHT, corner_radius=0)
        self.scene.pack(fill="both", expand=True)
        self.scene.canvas.configure(bg="#101827")
        Image(
            self.scene,
            image=make_checker_background(WIDTH, HEIGHT),
            width=WIDTH,
            height=HEIGHT,
            x=0,
            y=0,
            anchor="nw",
        ).show()
        
        Text(
            self.scene,
            text="Transparency / Opacity cookbook",
            font="Roboto 32 bold",
            fill="#ffffff",
            x=42,
            y=34,
            anchor="nw",
        ).show()
        Text(
            self.scene,
            text="Real alpha is done with Image(...).",
            font="Roboto 16",
            fill="#bad7ff",
            x=44,
            y=82,
            anchor="nw",
        ).show()

        # Pattern 1: a global transparent overlay.
        # This is useful for dimming a background without hiding it.
        self.dim_overlay = Image(
            self.scene,
            x=0,
            y=0,
            width=WIDTH,
            height=HEIGHT,
            anchor="nw",
            fg_color="#000000",
            opacity=0.18,
        )
        self.dim_overlay.show()

        self._draw_static_cards()
        self._draw_transparent_images()
        self._draw_live_card()

    def _transparent_card(
        self,
        *,
        x: int,
        y: int,
        width: int,
        height: int,
        opacity: float,
        title: str,
        body: str,
    ) -> Frame:
        """Create a transparent panel using a shared canvas."""
        card = Frame(
            self.scene,
            canvas=self.scene.canvas,  # Important: share the same canvas as the background.
            width=width,
            height=height,
            fg_color="transparent",
        )
        card.show()

        Image(
            card,
            x=x,
            y=y,
            width=width,
            height=height,
            anchor="nw",
            fg_color="#111827",
            opacity=opacity,
            border_radius=24,
            border_width=2,
            border_color="#8fd3ff",
        ).show()

        Text(card, text=title, font="Roboto 20 bold", fill="#ffffff", x=x + 24, y=y + 22, anchor="nw").show()
        Text(card, text=body, font="Roboto 14", fill="#d7e9ff", x=x + 24, y=y + 58, anchor="nw", width=width - 48).show()
        Text(
            card,
            text=f"opacity={opacity:.2f}",
            font="Roboto 14 bold",
            fill="#8ee6d2",
            x=x + 24,
            y=y + height - 40,
            anchor="nw",
        ).show()
        return card

    def _draw_static_cards(self) -> None:
        self._transparent_card(
            x=42,
            y=130,
            width=305,
            height=170,
            opacity=0.25,
            title="Very transparent",
            body="Use low opacity when you want the background to stay loud and visible.",
        )
        self._transparent_card(
            x=372,
            y=130,
            width=305,
            height=170,
            opacity=0.55,
            title="Balanced glass",
            body="This is usually the sweet spot for readable cards over artwork.",
        )
        self._transparent_card(
            x=702,
            y=130,
            width=305,
            height=170,
            opacity=0.88,
            title="Almost solid",
            body="Use high opacity when text readability matters more than the background.",
        )

    def _draw_transparent_images(self) -> None:
        Text(
            self.scene,
            text="Image opacity",
            font="Roboto 23 bold",
            fill="#ffffff",
            x=45,
            y=335,
            anchor="nw",
        ).show()

        icon = make_icon_image()
        Image(self.scene, image=icon, x=60, y=390, width=120, height=120, anchor="nw", opacity=1.00).show()
        Image(self.scene, image=icon, x=210, y=390, width=120, height=120, anchor="nw", opacity=0.60).show()
        Image(self.scene, image=icon, x=360, y=390, width=120, height=120, anchor="nw", opacity=0.25).show()

        Text(self.scene, text="1.00", font="Roboto 15 bold", fill="#ffffff", x=100, y=525, anchor="nw").show()
        Text(self.scene, text="0.60", font="Roboto 15 bold", fill="#ffffff", x=250, y=525, anchor="nw").show()
        Text(self.scene, text="0.25", font="Roboto 15 bold", fill="#ffffff", x=400, y=525, anchor="nw").show()

        Text(
            self.scene,
            text='Images use: Image(scene, image=image, opacity=0.60)',
            font="Roboto 15",
            fill="#bad7ff",
            x=45,
            y=565,
            anchor="nw",
        ).show()

    def _draw_live_card(self) -> None:
        self.live_opacity = 0.55
        self.live_card_x = 560
        self.live_card_y = 360
        self.live_card_width = 490
        self.live_card_height = 220

        self.live_card = Frame(
            self.scene,
            canvas=self.scene.canvas,
            width=self.live_card_width,
            height=self.live_card_height,
            fg_color="transparent",
        )
        self.live_card.show()
        self.live_card_background = Image(
            self.live_card,
            x=self.live_card_x,
            y=self.live_card_y,
            width=self.live_card_width,
            height=self.live_card_height,
            anchor="nw",
            fg_color="#111827",
            opacity=self.live_opacity,
            border_radius=28,
            border_width=2,
            border_color="#ffffff",
        )
        self.live_card_background.show()
        self.live_title = Text(
            self.live_card,
            text="Live opacity change",
            font="Roboto 23 bold",
            fill="#ffffff",
            x=self.live_card_x + 28,
            y=self.live_card_y + 24,
            anchor="nw",
        )
        self.live_title.show()
        self.live_text = Text(
            self.live_card,
            text="",
            font="Roboto 15",
            fill="#d7e9ff",
            x=self.live_card_x + 28,
            y=self.live_card_y + 68,
            anchor="nw",
            width=self.live_card_width - 56,
        )
        self.live_text.show()

        button_y = self.live_card_y + 148
        for index, value in enumerate((0.15, 0.35, 0.60, 0.90)):
            Button(
                self.live_card,
                x=self.live_card_x + 78 + index * 100,
                y=button_y,
                width=82,
                height=42,
                text=f"{value:.2f}",
                font="Roboto 13 bold",
                fg_color="#21496f",
                hover_color="#2f6699",
                select_color="#163450",
                border_radius=12,
                command=lambda selected=value: self.set_live_opacity(selected),
            ).show()

        self.set_live_opacity(self.live_opacity)

    def set_live_opacity(self, opacity: float) -> None:
        """Re-render the same card with a new background alpha value."""
        self.live_opacity = opacity
        self.live_card_background.configure(
            image=None,
            width=self.live_card_width,
            height=self.live_card_height,
            fg_color="#111827",
            opacity=opacity,
            border_radius=28,
            border_width=2,
            border_color="#ffffff",
        )
        self.live_card_background.move(self.live_card_x, self.live_card_y)
        self.live_text.set(
            "This card is updated with:\n"
            f'live_card_background.configure(fg_color="#111827", opacity={opacity:.2f})'
        )


def main() -> None:
    setup("Dark")
    app = OpacityExample()
    app.center_window()

    if "--smoke-test" in sys.argv:
        app.open()
        app.update_idletasks()
        app.update()
        assert app.scene.winfo_x() == 0 and app.scene.winfo_y() == 0
        assert app.scene.winfo_width() == app.canvas.winfo_width()
        assert app.scene.winfo_height() == app.canvas.winfo_height()
        assert app.dim_overlay._is_rendered
        assert app.live_card_background._is_rendered
        app.close()
    else:
        app.open()


if __name__ == "__main__":
    main()
