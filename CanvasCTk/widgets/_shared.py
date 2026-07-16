from __future__ import annotations

import math
import re
import threading
import time
import tkinter as tk
from collections import OrderedDict
from collections.abc import Callable, Mapping
from functools import lru_cache
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Any

import customtkinter as ctk
from customtkinter.windows.widgets.appearance_mode import AppearanceModeTracker
from PIL import Image as PILImage, ImageChops, ImageColor, ImageDraw, ImageEnhance, ImageFilter, ImageTk

from ..element import Element, ElementBase

IMAGE_EXTENSIONS = (".webp", ".png", ".jpg", ".jpeg")
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".webm")

_DECODED_IMAGE_CACHE_DEFAULT_ENTRIES = 128
_DECODED_IMAGE_CACHE_DEFAULT_BYTES = 128 * 1024 * 1024
_DECODED_IMAGE_CACHE_MAX_ENTRIES = _DECODED_IMAGE_CACHE_DEFAULT_ENTRIES
_DECODED_IMAGE_CACHE_MAX_BYTES = _DECODED_IMAGE_CACHE_DEFAULT_BYTES
_DECODED_IMAGE_CACHE_BYTES = 0
_DECODED_IMAGE_CACHE: OrderedDict[
    tuple[str, int, int], tuple[PILImage.Image, int]
] = OrderedDict()
_DECODED_IMAGE_CACHE_LOCK = threading.RLock()


def _appearance_color(color: Any, fallback: str = "#00000000") -> str:
    if color is None or color == "transparent":
        return fallback
    if isinstance(color, (tuple, list)):
        return str(color[1 if ctk.get_appearance_mode() == "Dark" else 0])
    return str(color)


def _master_background_color(master: Any, canvas: Any = None) -> Any:
    """Resolve the visible surface behind a child, like CTkBaseClass does.

    CanvasCTk frames are logical items on a shared canvas rather than real Tk
    frames.  Native CustomTkinter children therefore cannot discover their
    master's foreground through Tk's normal ``cget('bg')`` path unless we
    resolve the logical frame chain ourselves.
    """
    seen: set[int] = set()
    current = master
    while current is not None and id(current) not in seen:
        seen.add(id(current))

        try:
            foreground = current.cget("fg_color")
        except (AttributeError, KeyError, TypeError, ValueError, tk.TclError):
            foreground = None
        if foreground not in (None, "transparent"):
            # Preserve a light/dark tuple. Native CTk children store this as
            # their bg_color and select the active side on appearance changes.
            return foreground

        # Plain Tk parents expose their surface through bg/background.  Avoid
        # asking logical CanvasCTk objects for this until their fg has been
        # checked, because their bg alias intentionally resolves this chain.
        options = getattr(current, "_options", None)
        is_logical_canvas_surface = isinstance(options, dict) and "fg_color" in options
        if not is_logical_canvas_surface:
            for option in ("bg", "background"):
                try:
                    background = current.cget(option)
                except (AttributeError, KeyError, TypeError, ValueError, tk.TclError):
                    continue
                if background not in (None, "", "transparent"):
                    return background

        current = getattr(current, "master", None)

    fallback_canvas = canvas or getattr(master, "canvas", None)
    if fallback_canvas is not None:
        try:
            return str(fallback_canvas.cget("bg"))
        except (AttributeError, KeyError, TypeError, ValueError, tk.TclError):
            pass
    return "#FFFFFF" if ctk.get_appearance_mode() == "Light" else "#000000"


def _rgba_color(value: str) -> tuple[int, int, int, int]:
    try:
        return ImageColor.getcolor(value, "RGBA")
    except ValueError:
        match = re.fullmatch(r"gr(?:a|e)y(\d{1,3})", value.strip(), re.IGNORECASE)
        if match is None:
            raise

        percentage = max(0, min(100, int(match.group(1))))
        channel = round(255 * percentage / 100)
        return channel, channel, channel, 255


def _color_with_opacity(color: Any, opacity: float = 1, fallback: str = "#00000000") -> tuple[int, int, int, int]:
    value = _appearance_color(color, fallback)
    try:
        red, green, blue, alpha = _rgba_color(value)
    except ValueError:
        red, green, blue, alpha = _rgba_color(fallback)
    opacity = max(0.0, min(1.0, float(opacity)))
    return red, green, blue, max(0, min(255, int(alpha * opacity)))


def _composite_color(
    foreground: Any,
    background: Any,
    opacity: float = 1,
    fallback: str = "#000000",
) -> str:
    """Flatten an RGBA surface to the opaque color required by Tk editors."""
    foreground_rgba = _color_with_opacity(foreground, opacity, fallback)
    background_rgba = _color_with_opacity(background, 1, fallback)

    # Tk Entry/Text widgets require an opaque background. Flatten a possibly
    # translucent backing color first, then place the requested surface over it.
    fallback_rgba = _color_with_opacity(fallback, 1, "#000000")
    background_alpha = background_rgba[3] / 255
    background_rgb = tuple(
        round(background_rgba[index] * background_alpha + fallback_rgba[index] * (1 - background_alpha))
        for index in range(3)
    )
    foreground_alpha = foreground_rgba[3] / 255
    result = tuple(
        round(foreground_rgba[index] * foreground_alpha + background_rgb[index] * (1 - foreground_alpha))
        for index in range(3)
    )
    return "#{:02x}{:02x}{:02x}".format(*result)


def _padding_pair(value: Any) -> tuple[int, int]:
    if isinstance(value, (tuple, list)):
        return int(value[0]), int(value[1])
    value = int(value or 0)
    return value, value


def _padding_box(width: int, height: int, value: Any) -> tuple[int, int, int, int]:
    if isinstance(value, (tuple, list)):
        if len(value) == 4:
            left, top, right, bottom = map(int, value)
        elif len(value) == 2:
            left = right = int(value[0])
            top = bottom = int(value[1])
        elif len(value) == 1:
            left = top = right = bottom = int(value[0])
        else:
            raise ValueError("Padding must be a number, (x, y), or (left, top, right, bottom).")
    else:
        left = top = right = bottom = int(value or 0)

    max_x = max(0, width - 1)
    max_y = max(0, height - 1)
    x0 = max(0, min(max_x, left))
    y0 = max(0, min(max_y, top))
    x1 = max(x0, min(max_x, max_x - max(0, right)))
    y1 = max(y0, min(max_y, max_y - max(0, bottom)))
    return x0, y0, x1, y1


@lru_cache(maxsize=32)
def _rounded_corner_quadrants(radius: int) -> tuple[PILImage.Image, ...]:
    """Return antialiased alpha quarters for a rounded rectangle corner."""
    radius = max(1, int(radius))
    diameter = radius * 2
    scale = 4
    circle = PILImage.new("L", (diameter * scale, diameter * scale), 0)
    ImageDraw.Draw(circle).ellipse(
        (0, 0, diameter * scale - 1, diameter * scale - 1),
        fill=255,
    )
    circle = circle.resize((diameter, diameter), PILImage.Resampling.LANCZOS)
    return (
        circle.crop((0, 0, radius, radius)),
        circle.crop((radius, 0, diameter, radius)),
        circle.crop((radius, radius, diameter, diameter)),
        circle.crop((0, radius, radius, diameter)),
    )


def _draw_large_rounded_rectangle_mask(
    size: tuple[int, int],
    box: tuple[int, int, int, int],
    radius: int,
) -> PILImage.Image:
    """Draw only the small rounded corners at high resolution."""
    mask = PILImage.new("L", size, 0)
    x0, y0, x1, y1 = map(int, box)
    if x1 < x0 or y1 < y0:
        return mask
    radius = min(max(0, int(radius)), (x1 - x0 + 1) // 2, (y1 - y0 + 1) // 2)
    draw = ImageDraw.Draw(mask)
    if radius <= 0:
        draw.rectangle((x0, y0, x1, y1), fill=255)
        return mask

    draw.rectangle((x0 + radius, y0, x1 - radius, y1), fill=255)
    draw.rectangle((x0, y0 + radius, x1, y1 - radius), fill=255)
    top_left, top_right, bottom_right, bottom_left = _rounded_corner_quadrants(radius)
    mask.paste(top_left, (x0, y0))
    mask.paste(top_right, (x1 - radius + 1, y0))
    mask.paste(bottom_right, (x1 - radius + 1, y1 - radius + 1))
    mask.paste(bottom_left, (x0, y1 - radius + 1))
    return mask


def _draw_large_rounded_rectangle_image(
    size: tuple[int, int],
    box: tuple[int, int, int, int],
    radius: int,
    fill: Any = None,
    outline: Any = None,
    width: int = 1,
) -> PILImage.Image:
    layer = PILImage.new("RGBA", size, (0, 0, 0, 0))
    outer_mask = _draw_large_rounded_rectangle_mask(size, box, radius)
    if fill is not None:
        layer.paste(fill, (0, 0, size[0], size[1]), outer_mask)
    if outline is None:
        return layer

    inset = max(1, int(width))
    x0, y0, x1, y1 = box
    if x0 + inset <= x1 - inset and y0 + inset <= y1 - inset:
        inner_mask = _draw_large_rounded_rectangle_mask(
            size,
            (x0 + inset, y0 + inset, x1 - inset, y1 - inset),
            max(0, int(radius) - inset),
        )
        border_mask = ImageChops.subtract(outer_mask, inner_mask)
    else:
        border_mask = outer_mask
    layer.paste(outline, (0, 0, size[0], size[1]), border_mask)
    return layer


def _draw_rounded_rectangle_image(
    size: tuple[int, int],
    box: tuple[int, int, int, int],
    radius: int,
    fill: Any = None,
    outline: Any = None,
    width: int = 1,
) -> PILImage.Image:
    area = max(1, size[0]) * max(1, size[1])
    if area > 256 * 256 and radius > 0:
        return _draw_large_rounded_rectangle_image(size, box, radius, fill, outline, width)
    scale = (2 if area > 256 * 256 else 4) if radius > 0 or width > 1 else 1
    layer = PILImage.new("RGBA", (size[0] * scale, size[1] * scale), (0, 0, 0, 0))
    scaled_box = tuple(int(round(value * scale)) for value in box)
    ImageDraw.Draw(layer).rounded_rectangle(
        scaled_box,
        radius=max(0, int(radius * scale)),
        fill=fill,
        outline=outline,
        width=max(1, int(width * scale)),
    )
    if scale == 1:
        return layer
    # Large frame surfaces only need antialiasing around a small rounded edge.
    # Bilinear downsampling keeps that edge smooth without paying Lanczos's
    # disproportionate full-surface cost during initial geometry layout.
    resampling = PILImage.Resampling.BILINEAR if area > 256 * 256 else PILImage.Resampling.LANCZOS
    return layer.resize(size, resampling)


@lru_cache(maxsize=64)
def _cached_rounded_rectangle_image(
    size: tuple[int, int],
    box: tuple[int, int, int, int],
    radius: int,
    fill: Any,
    outline: Any,
    width: int,
) -> PILImage.Image:
    return _draw_rounded_rectangle_image(size, box, radius, fill, outline, width)


def _rounded_rectangle_image(
    size: tuple[int, int],
    box: tuple[int, int, int, int],
    radius: int,
    fill: Any = None,
    outline: Any = None,
    width: int = 1,
) -> PILImage.Image:
    normalized_size = tuple(map(int, size))
    normalized_box = tuple(map(int, box))
    normalized_fill = tuple(fill) if isinstance(fill, list) else fill
    normalized_outline = tuple(outline) if isinstance(outline, list) else outline
    args = (
        normalized_size,
        normalized_box,
        max(0, int(radius)),
        normalized_fill,
        normalized_outline,
        max(1, int(width)),
    )
    if normalized_size[0] * normalized_size[1] <= 256 * 256:
        return _cached_rounded_rectangle_image(*args)
    return _draw_rounded_rectangle_image(*args)


def _draw_rounded_rectangle_mask(
    size: tuple[int, int],
    box: tuple[int, int, int, int],
    radius: int,
) -> PILImage.Image:
    area = max(1, size[0]) * max(1, size[1])
    if area > 256 * 256 and radius > 0:
        return _draw_large_rounded_rectangle_mask(size, box, radius)
    scale = (2 if area > 256 * 256 else 4) if radius > 0 else 1
    mask = PILImage.new("L", (size[0] * scale, size[1] * scale), 0)
    scaled_box = tuple(int(round(value * scale)) for value in box)
    ImageDraw.Draw(mask).rounded_rectangle(
        scaled_box,
        radius=max(0, int(radius * scale)),
        fill=255,
    )
    if scale == 1:
        return mask
    resampling = PILImage.Resampling.BILINEAR if area > 256 * 256 else PILImage.Resampling.LANCZOS
    return mask.resize(size, resampling)


@lru_cache(maxsize=64)
def _cached_rounded_rectangle_mask(
    size: tuple[int, int],
    box: tuple[int, int, int, int],
    radius: int,
) -> PILImage.Image:
    return _draw_rounded_rectangle_mask(size, box, radius)


def _rounded_rectangle_mask(
    size: tuple[int, int],
    box: tuple[int, int, int, int],
    radius: int,
) -> PILImage.Image:
    normalized_size = tuple(map(int, size))
    args = normalized_size, tuple(map(int, box)), max(0, int(radius))
    if normalized_size[0] * normalized_size[1] <= 256 * 256:
        return _cached_rounded_rectangle_mask(*args)
    return _draw_rounded_rectangle_mask(*args)


def _resolve_path(owner: Element, source: str | Path, extensions: tuple[str, ...], kind: str) -> Path:
    path = Path(source).expanduser()
    if not path.is_absolute():
        path = owner.get_resource_path(path)
    if path.exists():
        return path
    if not path.suffix:
        for extension in extensions:
            candidate = path.with_suffix(extension)
            if candidate.exists():
                return candidate
    raise FileNotFoundError(f"{kind} not found: {path}")


def _decoded_image_size(image: PILImage.Image) -> int:
    """Return a conservative byte estimate for an in-memory Pillow image."""
    return max(1, int(image.width) * int(image.height) * len(image.getbands()))


def _trim_decoded_image_cache() -> None:
    global _DECODED_IMAGE_CACHE_BYTES
    while _DECODED_IMAGE_CACHE and (
        len(_DECODED_IMAGE_CACHE) > _DECODED_IMAGE_CACHE_MAX_ENTRIES
        or _DECODED_IMAGE_CACHE_BYTES > _DECODED_IMAGE_CACHE_MAX_BYTES
    ):
        _, (_, byte_size) = _DECODED_IMAGE_CACHE.popitem(last=False)
        _DECODED_IMAGE_CACHE_BYTES = max(0, _DECODED_IMAGE_CACHE_BYTES - byte_size)


def _clear_decoded_image_cache() -> None:
    global _DECODED_IMAGE_CACHE_BYTES
    with _DECODED_IMAGE_CACHE_LOCK:
        _DECODED_IMAGE_CACHE.clear()
        _DECODED_IMAGE_CACHE_BYTES = 0


def _configure_decoded_image_cache(
    *,
    max_entries: int | None = None,
    max_bytes: int | None = None,
    clear: bool = False,
) -> dict[str, int]:
    """Configure the byte-aware cache used for decoded still-image files."""
    global _DECODED_IMAGE_CACHE_MAX_ENTRIES, _DECODED_IMAGE_CACHE_MAX_BYTES
    global _DECODED_IMAGE_CACHE_BYTES
    with _DECODED_IMAGE_CACHE_LOCK:
        if max_entries is not None:
            max_entries = int(max_entries)
            if max_entries < 0:
                raise ValueError("decoded image cache max_entries cannot be negative")
            _DECODED_IMAGE_CACHE_MAX_ENTRIES = max_entries
        if max_bytes is not None:
            max_bytes = int(max_bytes)
            if max_bytes < 0:
                raise ValueError("decoded image cache max_bytes cannot be negative")
            _DECODED_IMAGE_CACHE_MAX_BYTES = max_bytes
        if clear:
            _DECODED_IMAGE_CACHE.clear()
            _DECODED_IMAGE_CACHE_BYTES = 0
        else:
            _trim_decoded_image_cache()
        return {
            "max_entries": _DECODED_IMAGE_CACHE_MAX_ENTRIES,
            "max_bytes": _DECODED_IMAGE_CACHE_MAX_BYTES,
            "entries": len(_DECODED_IMAGE_CACHE),
            "bytes": _DECODED_IMAGE_CACHE_BYTES,
        }


def _load_cached_image_file(path: str, modified_ns: int, file_size: int) -> PILImage.Image:
    """Decode an unchanged still-image file once and reuse its RGBA pixels."""
    global _DECODED_IMAGE_CACHE_BYTES
    key = str(path), int(modified_ns), int(file_size)
    with _DECODED_IMAGE_CACHE_LOCK:
        cached = _DECODED_IMAGE_CACHE.get(key)
        if cached is not None:
            _DECODED_IMAGE_CACHE.move_to_end(key)
            return cached[0]

    with PILImage.open(path) as source:
        image = source.convert("RGBA")
    byte_size = _decoded_image_size(image)

    with _DECODED_IMAGE_CACHE_LOCK:
        # A second caller may have populated the entry while this image was
        # decoded. Prefer that canonical object so every consumer can share it.
        cached = _DECODED_IMAGE_CACHE.get(key)
        if cached is not None:
            _DECODED_IMAGE_CACHE.move_to_end(key)
            return cached[0]
        if (
            _DECODED_IMAGE_CACHE_MAX_ENTRIES > 0
            and _DECODED_IMAGE_CACHE_MAX_BYTES > 0
            and byte_size <= _DECODED_IMAGE_CACHE_MAX_BYTES
        ):
            _DECODED_IMAGE_CACHE[key] = image, byte_size
            _DECODED_IMAGE_CACHE_BYTES += byte_size
            _trim_decoded_image_cache()
    return image


# Preserve the useful part of functools.lru_cache's testing/introspection API.
_load_cached_image_file.cache_clear = _clear_decoded_image_cache  # type: ignore[attr-defined]


def _is_video_source(owner: Element, source: str | Path | PILImage.Image | ctk.CTkImage | None) -> bool:
    if source is None or isinstance(source, (PILImage.Image, ctk.CTkImage)):
        return False
    path = Path(source)
    if path.suffix.lower() in VIDEO_EXTENSIONS:
        return True
    if not path.suffix:
        try:
            _resolve_path(owner, source, VIDEO_EXTENSIONS, "Video resource")
            return True
        except FileNotFoundError:
            return False
    return False


def _resolve_image(
    owner: Element,
    source: str | Path | PILImage.Image | ctk.CTkImage | None,
) -> PILImage.Image | None:
    if source is None:
        return None
    if isinstance(source, PILImage.Image):
        return source.copy().convert("RGBA")
    if isinstance(source, ctk.CTkImage):
        appearance = ctk.get_appearance_mode().lower()
        preferred = source.cget("dark_image" if appearance == "dark" else "light_image")
        fallback = source.cget("light_image" if appearance == "dark" else "dark_image")
        selected = preferred if preferred is not None else fallback
        return None if selected is None else selected.copy().convert("RGBA")
    path = _resolve_path(owner, source, IMAGE_EXTENSIONS, "Image resource")
    resolved = path.resolve()
    stat = resolved.stat()
    return _load_cached_image_file(str(resolved), stat.st_mtime_ns, stat.st_size)


def _position_canvas_text(
    canvas: tk.Canvas,
    item_id: int,
    x: float,
    y: float,
    anchor: str = "center",
) -> None:
    """Place text by its visible bbox instead of Tk's baseline-padded font box."""
    canvas.coords(item_id, x, y)
    bounds = canvas.bbox(item_id)
    if bounds is None:
        return
    left, top, right, bottom = bounds
    anchor = str(anchor or "center").lower()
    actual_x = left if anchor in {"w", "nw", "sw"} else right if anchor in {"e", "ne", "se"} else (left + right) / 2
    actual_y = top if anchor in {"n", "ne", "nw"} else bottom if anchor in {"s", "se", "sw"} else (top + bottom) / 2
    canvas.move(item_id, x - actual_x, y - actual_y)



__all__ = [
    "math",
    "re",
    "threading",
    "time",
    "tk",
    "Callable",
    "Mapping",
    "Path",
    "Empty",
    "Full",
    "Queue",
    "Any",
    "ctk",
    "AppearanceModeTracker",
    "PILImage",
    "ImageColor",
    "ImageChops",
    "ImageDraw",
    "ImageEnhance",
    "ImageFilter",
    "ImageTk",
    "Element",
    "ElementBase",
    "IMAGE_EXTENSIONS",
    "VIDEO_EXTENSIONS",
    "_appearance_color",
    "_composite_color",
    "_color_with_opacity",
    "_padding_pair",
    "_padding_box",
    "_rounded_rectangle_image",
    "_rounded_rectangle_mask",
    "_resolve_path",
    "_load_cached_image_file",
    "_configure_decoded_image_cache",
    "_clear_decoded_image_cache",
    "_is_video_source",
    "_resolve_image",
    "_position_canvas_text",
]
