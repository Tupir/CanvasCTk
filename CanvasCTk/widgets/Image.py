from collections import OrderedDict
from itertools import count
from weakref import WeakKeyDictionary, WeakValueDictionary, ref

from ._shared import *
from .Item import Item


_RENDERED_CACHE_DEFAULT_ENTRIES = 512
_RENDERED_CACHE_DEFAULT_BYTES = 64 * 1024 * 1024


class _RenderedPhotoCache:
    """Weak global index plus a globally bounded, interpreter-partitioned hot set."""

    def __init__(self) -> None:
        self.max_entries = _RENDERED_CACHE_DEFAULT_ENTRIES
        self.max_bytes = _RENDERED_CACHE_DEFAULT_BYTES
        self._weak: WeakValueDictionary[tuple[Any, ...], ImageTk.PhotoImage] = WeakValueDictionary()
        self._strong: dict[int, OrderedDict[tuple[Any, ...], tuple[ImageTk.PhotoImage, int]]] = {}
        self._bytes: dict[int, int] = {}
        self._global_order: OrderedDict[tuple[Any, ...], None] = OrderedDict()
        self._total_bytes = 0
        self._lock = threading.RLock()

    @staticmethod
    def _photo_bytes(photo: Any) -> int:
        try:
            return max(1, int(photo.width()) * int(photo.height()) * 4)
        except (AttributeError, TypeError, ValueError, tk.TclError):
            return 1

    @staticmethod
    def _interpreter_key(key: tuple[Any, ...]) -> int:
        return int(key[0])

    def _trim(self, _interpreter: int | None = None) -> None:
        while self._global_order and (
            len(self._global_order) > self.max_entries
            or self._total_bytes > self.max_bytes
        ):
            key, _ = self._global_order.popitem(last=False)
            interpreter = self._interpreter_key(key)
            hot = self._strong.get(interpreter)
            entry = hot.pop(key, None) if hot is not None else None
            if entry is None:
                continue
            size = entry[1]
            self._total_bytes = max(0, self._total_bytes - size)
            remaining = max(0, self._bytes.get(interpreter, 0) - size)
            if hot:
                self._bytes[interpreter] = remaining
            else:
                self._strong.pop(interpreter, None)
                self._bytes.pop(interpreter, None)

    def get(self, key: tuple[Any, ...], default: Any = None) -> Any:
        with self._lock:
            photo = self._weak.get(key)
            if photo is None:
                return default
            interpreter = self._interpreter_key(key)
            hot = self._strong.setdefault(interpreter, OrderedDict())
            previous = hot.pop(key, None)
            size = previous[1] if previous is not None else self._photo_bytes(photo)
            if previous is None:
                self._bytes[interpreter] = self._bytes.get(interpreter, 0) + size
                self._total_bytes += size
            hot[key] = photo, size
            self._global_order.pop(key, None)
            self._global_order[key] = None
            self._trim(interpreter)
            return photo

    def __setitem__(self, key: tuple[Any, ...], photo: ImageTk.PhotoImage) -> None:
        with self._lock:
            self._weak[key] = photo
            interpreter = self._interpreter_key(key)
            hot = self._strong.setdefault(interpreter, OrderedDict())
            previous = hot.pop(key, None)
            if previous is not None:
                self._bytes[interpreter] = max(
                    0, self._bytes.get(interpreter, 0) - previous[1]
                )
                self._total_bytes = max(0, self._total_bytes - previous[1])
                self._global_order.pop(key, None)
            size = self._photo_bytes(photo)
            if self.max_entries > 0 and self.max_bytes > 0 and size <= self.max_bytes:
                hot[key] = photo, size
                self._bytes[interpreter] = self._bytes.get(interpreter, 0) + size
                self._total_bytes += size
                self._global_order[key] = None
                self._trim(interpreter)
            elif not hot:
                self._strong.pop(interpreter, None)
                self._bytes.pop(interpreter, None)

    def clear(self, interpreter: int | None = None) -> None:
        with self._lock:
            if interpreter is None:
                self._weak.clear()
                self._strong.clear()
                self._bytes.clear()
                self._global_order.clear()
                self._total_bytes = 0
                return
            for key in tuple(self._weak.keys()):
                if self._interpreter_key(key) == interpreter:
                    self._weak.pop(key, None)
            hot = self._strong.pop(interpreter, None)
            if hot is not None:
                for key, (_photo, size) in hot.items():
                    self._global_order.pop(key, None)
                    self._total_bytes = max(0, self._total_bytes - size)
            self._bytes.pop(interpreter, None)

    def configure(
        self,
        *,
        max_entries: int | None = None,
        max_bytes: int | None = None,
        clear: bool = False,
    ) -> dict[str, int]:
        with self._lock:
            if max_entries is not None:
                max_entries = int(max_entries)
                if max_entries < 0:
                    raise ValueError("rendered image cache max_entries cannot be negative")
                self.max_entries = max_entries
            if max_bytes is not None:
                max_bytes = int(max_bytes)
                if max_bytes < 0:
                    raise ValueError("rendered image cache max_bytes cannot be negative")
                self.max_bytes = max_bytes
            if clear:
                self.clear()
            else:
                self._trim()
            return {
                "max_entries": self.max_entries,
                "max_bytes": self.max_bytes,
                "entries": sum(len(entries) for entries in self._strong.values()),
                "bytes": sum(self._bytes.values()),
            }


_PHOTO_IMAGE_CACHE = _RenderedPhotoCache()
_CACHE_ROOT_BINDINGS: set[int] = set()
_OBJECT_CACHE_TOKENS: dict[int, tuple[Any, int]] = {}
_OBJECT_CACHE_TOKEN_COUNTER = count(1)
_CTK_IMAGE_REVISIONS: WeakKeyDictionary[Any, tuple[Any, Any, int]] = WeakKeyDictionary()


def _object_cache_token(value: Any) -> int:
    identity = id(value)
    cached = _OBJECT_CACHE_TOKENS.get(identity)
    if cached is not None and cached[0]() is value:
        return cached[1]
    token = next(_OBJECT_CACHE_TOKEN_COUNTER)

    def release(reference: Any, object_id: int = identity) -> None:
        current = _OBJECT_CACHE_TOKENS.get(object_id)
        if current is not None and current[0] is reference:
            _OBJECT_CACHE_TOKENS.pop(object_id, None)

    try:
        reference = ref(value, release)
    except TypeError:
        return identity
    _OBJECT_CACHE_TOKENS[identity] = reference, token
    return token


def _ctk_image_revision(source: ctk.CTkImage) -> int:
    light_cache = getattr(source, "_scaled_light_photo_images", None)
    dark_cache = getattr(source, "_scaled_dark_photo_images", None)
    try:
        cached = _CTK_IMAGE_REVISIONS.get(source)
        if cached is None:
            _CTK_IMAGE_REVISIONS[source] = light_cache, dark_cache, 0
            return 0
        previous_light, previous_dark, revision = cached
        if previous_light is not light_cache or previous_dark is not dark_cache:
            revision += 1
            _CTK_IMAGE_REVISIONS[source] = light_cache, dark_cache, revision
        return revision
    except TypeError:
        # Custom CTkImage implementations are normally weak-referenceable. A
        # conservative identity fallback still preserves current CTk behavior.
        return 0


def _ensure_cache_cleanup(canvas: Any) -> None:
    interpreter = id(canvas.tk)
    if interpreter in _CACHE_ROOT_BINDINGS:
        return
    try:
        root = canvas._root()
    except (AttributeError, tk.TclError):
        return

    def cleanup(event: Any, interpreter_key: int = interpreter) -> None:
        try:
            is_root = event.widget is event.widget._root()
        except (AttributeError, tk.TclError):
            is_root = True
        if is_root:
            _PHOTO_IMAGE_CACHE.clear(interpreter_key)
            _CACHE_ROOT_BINDINGS.discard(interpreter_key)

    try:
        root.bind("<Destroy>", cleanup, add="+")
        _CACHE_ROOT_BINDINGS.add(interpreter)
    except tk.TclError:
        pass


def configure_image_cache(
    rendered_max_entries: int = 512,
    rendered_max_mb: float = 64,
    decoded_max_entries: int = 128,
    decoded_max_mb: float = 128,
) -> dict[str, dict[str, int]]:
    """Configure CanvasCTk's still-image caches.

    Cache limits are hot-retention budgets: live widgets keep their own images
    after an LRU entry is evicted, so eviction never blanks an existing widget.
    Setting an entry or memory limit to zero disables that strong cache tier;
    weak sharing between currently live widgets remains active.
    """
    if float(rendered_max_mb) < 0:
        raise ValueError("rendered_max_mb cannot be negative")
    if float(decoded_max_mb) < 0:
        raise ValueError("decoded_max_mb cannot be negative")
    rendered_bytes = int(float(rendered_max_mb) * 1024 * 1024)
    decoded_bytes = int(float(decoded_max_mb) * 1024 * 1024)
    return {
        "rendered": _PHOTO_IMAGE_CACHE.configure(
            max_entries=rendered_max_entries,
            max_bytes=rendered_bytes,
        ),
        "decoded": _configure_decoded_image_cache(
            max_entries=decoded_max_entries,
            max_bytes=decoded_bytes,
        ),
    }


def _get_cached_resized_photo(
    owner: Any,
    source: str | Path | PILImage.Image,
    size: tuple[int, int],
) -> ImageTk.PhotoImage:
    """Return a cached immutable-path photo or a local mutable-PIL photo."""
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    _ensure_cache_cleanup(owner.canvas)
    cache_key: tuple[Any, ...] | None = None
    if isinstance(source, PILImage.Image):
        image = source.copy().convert("RGBA")
    else:
        path = _resolve_path(owner, source, IMAGE_EXTENSIONS, "Image resource").resolve()
        stat = path.stat()
        image = _load_cached_image_file(str(path), stat.st_mtime_ns, stat.st_size)
        cache_key = (
            id(owner.tk),
            "resized-path",
            str(path),
            stat.st_mtime_ns,
            stat.st_size,
            width,
            height,
        )
        cached = _PHOTO_IMAGE_CACHE.get(cache_key)
        if cached is not None:
            return cached
    if image.size != (width, height):
        image = image.resize((width, height), PILImage.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(image, master=owner.canvas)
    if cache_key is not None:
        _PHOTO_IMAGE_CACHE[cache_key] = photo
    return photo


def _freeze_cache_value(value: Any) -> Any:
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_cache_value(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze_cache_value(item)) for key, item in value.items()))
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value


class Image(Item):
    """Canvas image widget with opacity, rounded backgrounds, and optional video playback."""

    def __init__(
        self,
        master: Any,
        canvas: tk.Canvas | None = None,
        image: str | Path | PILImage.Image | ctk.CTkImage | None = None,
        width: int = 64,
        height: int = 64,
        anchor: str = "center",
        opacity: float = 1,
        brightness: float = 1,
        fg_color: Any = None,
        border_radius: int = 0,
        border_width: int = 0,
        border_color: Any = None,
        border_padding: Any = 2,
        shadow_border: int = 0,
        shadow_color: Any = "#000000",
        shadow_opacity: float = 0.45,
        shadow_blur: float | None = None,
        bg_opacity: float = 1,
        padx: Any = 0,
        pady: Any = 0,
        video: bool | None = None,
        video_loop: bool = True,
        video_autoplay: bool = True,
        video_fps: float | None = None,
        video_cache_mb: float = 256,
        video_preload_seconds: float = 0.35,
        size: tuple[int, int] | None = None,
        x: int = 0,
        y: int = 0,
        **kwargs: Any,
    ) -> None:
        if size is not None:
            width, height = size
        corner_radius = kwargs.pop("corner_radius", None)
        if corner_radius is not None:
            border_radius = corner_radius
        super().__init__(master, canvas, **kwargs)
        self._size_follows_ctk_image = size is None and isinstance(image, ctk.CTkImage) and (width, height) == (64, 64)
        if self._size_follows_ctk_image:
            width, height = image.cget("size")
        self.image = image
        self._x, self._y = int(x), int(y)
        self._width, self._height = int(width), int(height)
        self._desired_width, self._desired_height = self._width, self._height
        self._anchor = anchor
        self.opacity = float(opacity)
        self.brightness = float(brightness)
        self.fg_color = fg_color
        self.border_radius = int(border_radius)
        self.border_width = int(border_width)
        self.border_color = border_color
        self.border_padding = border_padding
        self.shadow_border = max(0, int(shadow_border))
        self.shadow_color = shadow_color
        self.shadow_opacity = max(0.0, min(1.0, float(shadow_opacity)))
        self.shadow_blur = None if shadow_blur is None else max(0.0, float(shadow_blur))
        self._shadow_cache_key: tuple[Any, ...] | None = None
        self._shadow_cache: PILImage.Image | None = None
        self.bg_opacity = float(bg_opacity)
        self.padx = padx
        self.pady = pady
        self.video_loop = bool(video_loop)
        self.video_autoplay = bool(video_autoplay)
        self._video_fps_override = float(video_fps) if video_fps is not None else None
        self.video_fps = self._video_fps_override
        if self._video_fps_override is not None and self._video_fps_override <= 0:
            raise ValueError("video_fps must be greater than zero.")
        self.video_cache_mb = float(video_cache_mb)
        if self.video_cache_mb <= 0:
            raise ValueError("video_cache_mb must be greater than zero.")
        self.video_preload_seconds = float(video_preload_seconds)
        if self.video_preload_seconds < 0:
            raise ValueError("video_preload_seconds cannot be negative.")
        self._photo: ImageTk.PhotoImage | None = None
        self._photo_is_shared = False
        self._event_surface_enabled = False
        self._render_deferred = False
        self._source_image: PILImage.Image | None = None
        self._video_after_id: str | None = None
        self._video_autoplay_after_id: str | None = None
        self._video_backend: str | None = None
        self._video_path: Path | None = None
        self._video_reader: Any = None
        self._video_iterator: Any = None
        self._video_capture: Any = None
        self._video_is_playing = False
        self._video_next_frame_at: float | None = None
        self._video_source_fps = 30.0
        self._video_frame_queue: Queue[PILImage.Image] | None = None
        self._video_decode_stop: threading.Event | None = None
        self._video_decode_pause = threading.Event()
        self._video_decode_eof: threading.Event | None = None
        self._video_cache_complete: threading.Event | None = None
        self._video_decode_thread: threading.Thread | None = None
        self._video_preload_frames = 1
        self._video_buffering = True
        self._video_full_cache = False
        self._video_frame_cache: list[PILImage.Image] = []
        self._video_cache_index = 0
        self._is_video = False
        self._ctk_image_source: ctk.CTkImage | None = None
        self._appearance_tracker_registered = False
        self._last_rendered_appearance: str | None = None
        self._source_cache_key: tuple[Any, ...] | None = ("empty",)
        self._video_needs_open = False
        self._video_resume_on_show = False
        self._video_autoplay_pending = False

        self._load_source(image, video)

        self._image_id = self.canvas.create_image(x, y, anchor=anchor, state="hidden")
        _ensure_cache_cleanup(self.canvas)
        self._render()

    def _set_appearance_mode(self, _: str | None = None) -> None:
        if not self._is_rendered:
            self._render_deferred = True
            return
        appearance = ctk.get_appearance_mode()
        if appearance == self._last_rendered_appearance and not self._render_deferred:
            return
        if isinstance(self.image, ctk.CTkImage):
            self._source_image = _resolve_image(self, self.image)
            self._source_cache_key = self._still_source_cache_key(self.image)
        self._render()

    @staticmethod
    def _has_appearance_pair(color: Any) -> bool:
        return isinstance(color, (tuple, list)) and len(color) >= 2

    def _appearance_dependent(self) -> bool:
        return isinstance(self.image, ctk.CTkImage) or any(
            self._has_appearance_pair(color)
            for color in (self.fg_color, self.border_color, self.shadow_color)
        )

    def _update_appearance_tracker(self) -> None:
        needed = self._is_rendered and self._appearance_dependent()
        if needed and not self._appearance_tracker_registered:
            AppearanceModeTracker.add(self._set_appearance_mode, self.canvas)
            self._appearance_tracker_registered = True
        elif not needed and self._appearance_tracker_registered:
            AppearanceModeTracker.remove(self._set_appearance_mode)
            self._appearance_tracker_registered = False

    def _on_widget_scaling_changed(self, old_scaling: float, new_scaling: float) -> None:
        super()._on_widget_scaling_changed(old_scaling, new_scaling)
        if hasattr(self, "_image_id"):
            self._render()

    def _detach_ctk_image_callback(self) -> None:
        if self._ctk_image_source is None:
            return
        try:
            self._ctk_image_source.remove_configure_callback(self._ctk_image_changed)
        except ValueError:
            pass
        self._ctk_image_source = None

    def _ctk_image_changed(self) -> None:
        if not isinstance(self.image, ctk.CTkImage):
            return
        if self._size_follows_ctk_image:
            width, height = map(int, self.image.cget("size"))
            self._desired_width, self._desired_height = width, height
            if not self._layout_manager:
                self._width, self._height = width, height
        self._source_image = _resolve_image(self, self.image)
        self._source_cache_key = self._still_source_cache_key(self.image)
        self._render()
        if self._canvas_host is not None and self._layout_manager:
            self._canvas_host._schedule_child_layout()
        elif self._layout_manager:
            self._schedule_canvas_layout()

    def _base_image(self) -> PILImage.Image:
        width = max(1, int(round(self._apply_widget_scaling(self._width))))
        height = max(1, int(round(self._apply_widget_scaling(self._height))))
        radius = max(0, int(round(self._apply_widget_scaling(self.border_radius))))
        padx_x, _ = _padding_pair(self.padx)
        pady_y, _ = _padding_pair(self.pady)
        padx_x = max(0, int(round(self._apply_widget_scaling(padx_x))))
        pady_y = max(0, int(round(self._apply_widget_scaling(pady_y))))
        border_padding = self._scaled_padding(self.border_padding)
        border_width = max(0, int(round(self._apply_widget_scaling(self.border_width))))
        image: PILImage.Image | None = None

        if self._source_image is not None:
            content_width = max(1, width - padx_x * 2)
            content_height = max(1, height - pady_y * 2)
            target_size = (content_width, content_height)
            needs_resize = self._source_image.size != target_size
            if (
                not needs_resize
                and self.brightness == 1
                and self.opacity == 1
                and self.fg_color is None
                and padx_x == 0
                and pady_y == 0
                and radius == 0
                and not (self.border_width > 0 and self.border_color is not None)
                and self.shadow_border <= 0
            ):
                return self._source_image
            if self._source_image.mode == "RGBA":
                image = self._source_image
            else:
                image = self._source_image.convert("RGBA")
            if needs_resize:
                resampling = PILImage.Resampling.BILINEAR if self._is_video else PILImage.Resampling.LANCZOS
                image = image.resize(target_size, resampling)
            elif self.brightness != 1 or self.opacity != 1 or radius > 0:
                image = image.copy()
            if self.brightness != 1:
                image = ImageEnhance.Brightness(image).enhance(self.brightness)
            if self.opacity != 1:
                alpha = image.getchannel("A").point(lambda pixel: int(pixel * max(0.0, min(1.0, self.opacity))))
                image.putalpha(alpha)
            if radius > 0:
                content_radius = min(
                    max(0, radius - min(padx_x, pady_y)),
                    content_width // 2,
                    content_height // 2,
                )
                mask = _rounded_rectangle_mask(
                    (content_width, content_height),
                    _padding_box(content_width, content_height, border_padding),
                    content_radius,
                )
                alpha = PILImage.composite(
                    image.getchannel("A"),
                    PILImage.new("L", (content_width, content_height), 0),
                    mask,
                )
                image.putalpha(alpha)

            if (
                self.fg_color is None
                and padx_x == 0
                and pady_y == 0
                and radius == 0
                and not (border_width > 0 and self.border_color is not None)
                and self.shadow_border <= 0
            ):
                return image

        image_fills_result = image is not None and self.fg_color is None and padx_x == 0 and pady_y == 0
        if image_fills_result:
            result = image if image is not self._source_image else image.copy()
        else:
            result = PILImage.new("RGBA", (width, height), (0, 0, 0, 0))
        if self.fg_color is not None:
            result.alpha_composite(_rounded_rectangle_image(
                (width, height),
                (0, 0, width - 1, height - 1),
                fill=_color_with_opacity(self.fg_color, self.opacity * self.bg_opacity),
                radius=radius,
            ))
        if image is not None and not image_fills_result:
            result.alpha_composite(image, (padx_x, pady_y))

        shadow = self._shadow_overlay(width, height, radius)
        if shadow is not None:
            result.alpha_composite(shadow)

        if border_width > 0 and self.border_color is not None:
            result.alpha_composite(_rounded_rectangle_image(
                (width, height),
                (0, 0, width - 1, height - 1),
                outline=_color_with_opacity(self.border_color, self.opacity),
                radius=radius,
                width=border_width,
            ))

        return result

    def _scaled_padding(self, value: Any) -> Any:
        if isinstance(value, (tuple, list)):
            return tuple(int(round(self._apply_widget_scaling(part))) for part in value)
        return int(round(self._apply_widget_scaling(value or 0)))

    def _shadow_overlay(self, width: int, height: int, radius: int) -> PILImage.Image | None:
        shadow_border = max(
            0,
            min(int(round(self._apply_widget_scaling(self.shadow_border))), max(width, height)),
        )
        if shadow_border <= 0 or self.shadow_opacity <= 0:
            return None

        blur = (
            self._apply_widget_scaling(self.shadow_blur)
            if self.shadow_blur is not None
            else max(0.0, shadow_border / 3)
        )
        color = _appearance_color(self.shadow_color, "#000000")
        cache_key = (width, height, radius, shadow_border, color, self.shadow_opacity, blur, self.opacity)
        if cache_key == self._shadow_cache_key and self._shadow_cache is not None:
            return self._shadow_cache

        alpha = PILImage.new("L", (width, height), 0)
        draw = ImageDraw.Draw(alpha)
        max_alpha = int(255 * self.shadow_opacity)
        for inset in range(shadow_border):
            fade = 1 - (inset / max(1, shadow_border))
            value = max(0, min(255, int(max_alpha * fade)))
            if value <= 0:
                continue
            right = width - 1 - inset
            bottom = height - 1 - inset
            if right < inset or bottom < inset:
                break
            draw.rounded_rectangle(
                (inset, inset, right, bottom),
                radius=max(0, radius - inset),
                outline=value,
                width=1,
            )

        if blur > 0:
            alpha = alpha.filter(ImageFilter.GaussianBlur(blur))

        if radius > 0:
            clip = PILImage.new("L", (width, height), 0)
            ImageDraw.Draw(clip).rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=255)
            alpha = PILImage.composite(alpha, PILImage.new("L", (width, height), 0), clip)

        red, green, blue, color_alpha = _color_with_opacity(self.shadow_color, self.opacity)
        alpha = alpha.point(lambda pixel: max(0, min(255, int(pixel * color_alpha / 255))))
        overlay = PILImage.new("RGBA", (width, height), (red, green, blue, 0))
        overlay.putalpha(alpha)
        self._shadow_cache_key = cache_key
        self._shadow_cache = overlay
        return overlay

    @staticmethod
    def _color_is_visible(color: Any, opacity: float) -> bool:
        """Return whether *color* contributes a visible pixel in the active mode."""
        if color is None or color == "transparent" or opacity <= 0:
            return False
        return _color_with_opacity(color, opacity)[3] > 0

    def _is_visually_empty(self) -> bool:
        """Fast path for logical layers which have nothing to rasterize.

        Frames and compound widgets intentionally use ``Image`` instances as
        transparent layout/event layers.  Creating a full-size RGBA image and a
        Tk ``PhotoImage`` for each one is unnecessary; the existing canvas image
        item can remain image-less until a later ``configure`` call makes the
        layer visible.
        """
        if self.opacity <= 0:
            return True
        if self._source_image is not None:
            return False
        if self._color_is_visible(self.fg_color, self.opacity * self.bg_opacity):
            return False
        if (
            self.border_width > 0
            and self._color_is_visible(self.border_color, self.opacity)
        ):
            return False
        if (
            self.shadow_border > 0
            and self.shadow_opacity > 0
            and self._color_is_visible(
                self.shadow_color,
                self.opacity * self.shadow_opacity,
            )
        ):
            return False
        return True

    def _still_source_cache_key(
        self,
        source: str | Path | PILImage.Image | ctk.CTkImage | None,
    ) -> tuple[Any, ...] | None:
        if source is None:
            return ("empty",)
        if isinstance(source, PILImage.Image):
            # PIL images are mutable and do not provide change notifications.
            # Keep them widget-local so an in-place edit cannot return stale
            # pixels from a shared rendered-image cache.
            return None
        if isinstance(source, ctk.CTkImage):
            appearance = ctk.get_appearance_mode().lower()
            preferred = source.cget("dark_image" if appearance == "dark" else "light_image")
            fallback = source.cget("light_image" if appearance == "dark" else "dark_image")
            selected = preferred if preferred is not None else fallback
            return (
                "ctk",
                _object_cache_token(selected),
                getattr(selected, "size", None),
                _ctk_image_revision(source),
            )
        path = _resolve_path(self, source, IMAGE_EXTENSIONS, "Image resource").resolve()
        stat = path.stat()
        return ("path", str(path), stat.st_mtime_ns, stat.st_size)

    def _render_cache_key(self) -> tuple[Any, ...] | None:
        source_cache_key = getattr(self, "_source_cache_key", None)
        if getattr(self, "_is_video", False) or source_cache_key is None:
            return None
        width = max(1, int(round(self._apply_widget_scaling(self._width))))
        height = max(1, int(round(self._apply_widget_scaling(self._height))))
        if self._is_visually_empty() and self._event_surface_enabled:
            return id(self.tk), "event-surface", width, height

        has_source = self._source_image is not None
        radius = max(0, int(round(self._apply_widget_scaling(self.border_radius))))
        border_width = max(0, int(round(self._apply_widget_scaling(self.border_width))))
        padx_x, _ = _padding_pair(self.padx)
        pady_y, _ = _padding_pair(self.pady)
        physical_padx = max(0, int(round(self._apply_widget_scaling(padx_x)))) if has_source else 0
        physical_pady = max(0, int(round(self._apply_widget_scaling(pady_y)))) if has_source else 0
        foreground = (
            _color_with_opacity(self.fg_color, self.opacity * self.bg_opacity)
            if self._color_is_visible(self.fg_color, self.opacity * self.bg_opacity)
            else None
        )
        border = (
            _color_with_opacity(self.border_color, self.opacity)
            if border_width > 0 and self._color_is_visible(self.border_color, self.opacity)
            else None
        )
        shadow_border = max(0, int(round(self._apply_widget_scaling(self.shadow_border))))
        shadow = None
        shadow_blur = None
        if (
            shadow_border > 0
            and self.shadow_opacity > 0
            and self._color_is_visible(self.shadow_color, self.opacity * self.shadow_opacity)
        ):
            shadow = _color_with_opacity(
                self.shadow_color,
                self.opacity * self.shadow_opacity,
            )
            shadow_blur = (
                self._apply_widget_scaling(self.shadow_blur)
                if self.shadow_blur is not None
                else max(0.0, shadow_border / 3)
            )
        return (
            id(self.tk),
            source_cache_key,
            width,
            height,
            radius,
            foreground,
            border_width if border is not None else 0,
            border,
            shadow_border if shadow is not None else 0,
            shadow,
            shadow_blur,
            self.opacity if has_source else None,
            self.brightness if has_source else None,
            self._scaled_padding(self.border_padding) if has_source and radius > 0 else None,
            physical_padx,
            physical_pady,
        )

    def _render(self) -> None:
        if self._is_visually_empty() and not self._event_surface_enabled:
            self._render_deferred = False
            # Detach a previous visible image so configure(...="transparent")
            # releases its Tk/Pillow allocation as well as avoiding new ones.
            if self._photo is not None:
                self.canvas.itemconfigure(self._image_id, image="")
                self._photo = None
                self._photo_is_shared = False
            self.canvas.coords(self._image_id, *self._physical_point(self._x, self._y))
            return

        # Frames and compound controls are created before their logical host is
        # necessarily visible. Avoid rasterizing every inactive tab up front;
        # the first show renders the current state instead.
        if (
            not getattr(self, "_is_rendered", False)
            or (
                getattr(self, "_canvas_host", None) is not None
                and not self._host_is_rendered()
            )
        ):
            self._render_deferred = True
            self.canvas.coords(self._image_id, *self._physical_point(self._x, self._y))
            return

        self._render_deferred = False
        self._last_rendered_appearance = ctk.get_appearance_mode()
        cache_key = self._render_cache_key()
        if cache_key is not None:
            cached_photo = _PHOTO_IMAGE_CACHE.get(cache_key)
            if cached_photo is not None:
                if self._photo is not cached_photo:
                    self._photo = cached_photo
                    self.canvas.itemconfigure(self._image_id, image=self._photo)
                self._photo_is_shared = True
                self.canvas.coords(self._image_id, *self._physical_point(self._x, self._y))
                return

        image = self._base_image()
        if cache_key is not None:
            self._photo = ImageTk.PhotoImage(image, master=self.canvas)
            _PHOTO_IMAGE_CACHE[cache_key] = self._photo
            self._photo_is_shared = True
            self.canvas.itemconfigure(self._image_id, image=self._photo)
        elif (
            self._photo is not None
            and not getattr(self, "_photo_is_shared", False)
            and self._photo.width() == image.width
            and self._photo.height() == image.height
        ):
            self._photo.paste(image)
        else:
            self._photo = ImageTk.PhotoImage(image, master=self.canvas)
            self._photo_is_shared = False
            self.canvas.itemconfigure(self._image_id, image=self._photo)
        self.canvas.coords(self._image_id, *self._physical_point(self._x, self._y))

    def _enable_event_surface(self) -> None:
        """Keep an otherwise transparent image as a rectangular hit target.

        The rendered transparent PhotoImage is shared by the existing image
        cache, so identical controls retain reliable full-area hit testing
        without allocating a unique bitmap for every widget.
        """
        if self._event_surface_enabled:
            return
        self._event_surface_enabled = True
        self._render()

    def configure(self, **kwargs: Any) -> None:
        marker = object()
        image_value = kwargs.pop("image", marker)
        video_value = kwargs.pop("video", marker)
        requested_source = self.image if image_value is marker else image_value
        requested_video = getattr(self, "_video_requested", None) if video_value is marker else video_value
        current_source = getattr(self, "image", None)
        same_source = requested_source is current_source or (
            isinstance(requested_source, (str, Path))
            and isinstance(current_source, (str, Path))
            and Path(requested_source) == Path(current_source)
        )
        source_changed = not same_source or requested_video != getattr(self, "_video_requested", None)
        visual_changed = source_changed
        position_changed = False
        decoder_size_changed = False
        preload_changed = False
        was_playing = self._video_is_playing

        for key, value in kwargs.items():
            if key == "width":
                value = int(value)
                if value != self._desired_width or value != self._width:
                    self._desired_width = self._width = value
                    visual_changed = True
                    decoder_size_changed = True
            elif key == "height":
                value = int(value)
                if value != self._desired_height or value != self._height:
                    self._desired_height = self._height = value
                    visual_changed = True
                    decoder_size_changed = True
            elif key == "size":
                width, height = map(int, value)
                if (
                    (width, height) != (self._desired_width, self._desired_height)
                    or (width, height) != (self._width, self._height)
                ):
                    self._desired_width, self._desired_height = width, height
                    self._width, self._height = width, height
                    visual_changed = True
                    decoder_size_changed = True
            elif key in ("border_radius", "corner_radius"):
                value = int(value)
                if value != self.border_radius:
                    self.border_radius = value
                    visual_changed = True
            elif key == "x":
                value = int(value)
                if value != self._x:
                    self._x = value
                    position_changed = True
            elif key == "y":
                value = int(value)
                if value != self._y:
                    self._y = value
                    position_changed = True
            elif key == "anchor":
                value = str(value)
                if value != self._anchor:
                    self._set_anchor(value)
            elif key == "video_fps":
                fps = None if value is None else float(value)
                if fps is not None and fps <= 0:
                    raise ValueError("video_fps must be greater than zero.")
                if fps != self._video_fps_override:
                    self._video_fps_override = fps
                    self.video_fps = fps if fps is not None else self._video_source_fps
                    preload_changed = True
            elif key == "video_cache_mb":
                cache_mb = float(value)
                if cache_mb <= 0:
                    raise ValueError("video_cache_mb must be greater than zero.")
                if cache_mb != self.video_cache_mb:
                    self.video_cache_mb = cache_mb
                    decoder_size_changed = True
            elif key == "video_preload_seconds":
                preload_seconds = float(value)
                if preload_seconds < 0:
                    raise ValueError("video_preload_seconds cannot be negative.")
                if preload_seconds != self.video_preload_seconds:
                    self.video_preload_seconds = preload_seconds
                    preload_changed = True
            elif key in ("padx", "pady"):
                if value != getattr(self, key):
                    setattr(self, key, value)
                    visual_changed = True
                    decoder_size_changed = True
            elif key == "border_padding":
                if value != self.border_padding:
                    self.border_padding = value
                    visual_changed = True
            elif key in ("shadow_border", "shadow_width"):
                value = max(0, int(value))
                if value != self.shadow_border:
                    self.shadow_border = value
                    visual_changed = True
            elif key == "shadow_color":
                if value != self.shadow_color:
                    self.shadow_color = value
                    visual_changed = True
            elif key == "shadow_opacity":
                value = max(0.0, min(1.0, float(value)))
                if value != self.shadow_opacity:
                    self.shadow_opacity = value
                    visual_changed = True
            elif key == "shadow_blur":
                value = None if value is None else max(0.0, float(value))
                if value != self.shadow_blur:
                    self.shadow_blur = value
                    visual_changed = True
            elif key in ("video_loop", "video_autoplay"):
                setattr(self, key, bool(value))
            elif hasattr(self, key):
                if value != getattr(self, key):
                    setattr(self, key, value)
                    visual_changed = True

        should_play = False
        if source_changed:
            self._load_source(requested_source, requested_video)
            should_play = self._is_video and self.video_autoplay
        elif self._is_video and decoder_size_changed:
            self.pause_video()
            if self._is_rendered:
                self._open_video()
                self._video_needs_open = False
                should_play = was_playing
            else:
                self._video_needs_open = True
                self._video_resume_on_show = was_playing

        self._update_appearance_tracker()
        if preload_changed:
            self._update_video_preload_size()
        if visual_changed:
            self._render()
        elif position_changed:
            self.canvas.coords(self._image_id, *self._physical_point(self._x, self._y))
        if should_play:
            self._queue_video_autoplay()

    config = configure

    def set_image(self, image: str | Path | PILImage.Image | None) -> None:
        self.configure(image=image)

    def move(self, x: int, y: int) -> None:
        self._x, self._y = int(x), int(y)
        self.canvas.coords(self._image_id, *self._physical_point(self._x, self._y))

    def _set_anchor(self, anchor: str) -> None:
        self._anchor = anchor
        self.canvas.itemconfigure(self._image_id, anchor=anchor)

    def _apply_geometry_allocation(
        self,
        width: int | None,
        height: int | None,
    ) -> None:
        target_width = self._desired_width if width is None else max(1, int(width))
        target_height = self._desired_height if height is None else max(1, int(height))
        if (target_width, target_height) == (self._width, self._height):
            return

        was_playing = self._video_is_playing
        self._width, self._height = target_width, target_height
        if self._is_video:
            self.pause_video()
            if self._is_rendered:
                self._open_video()
                self._video_needs_open = False
            else:
                self._video_needs_open = True
                self._video_resume_on_show = was_playing
        self._render()
        if self._is_video and was_playing and self._is_rendered:
            self._queue_video_autoplay()

    def _resize_for_place(self, width: int | None, height: int | None) -> None:
        self._apply_geometry_allocation(width, height)

    def winfo_reqwidth(self) -> int:
        return max(1, int(round(self._apply_widget_scaling(self._desired_width))))

    def winfo_reqheight(self) -> int:
        return max(1, int(round(self._apply_widget_scaling(self._desired_height))))

    def cget(self, attribute_name: str) -> Any:
        if attribute_name == "width":
            return self._desired_width
        if attribute_name == "height":
            return self._desired_height
        if attribute_name == "size":
            return self._desired_width, self._desired_height
        if attribute_name == "image":
            return self.image
        raise ValueError(f"Unsupported Image option: {attribute_name!r}")

    def place(
        self,
        x: int | None = None,
        y: int | None = None,
        relx: float | None = None,
        rely: float | None = None,
        width: Any = None,
        height: Any = None,
        relwidth: Any = None,
        relheight: Any = None,
        anchor: str | None = None,
        **kwargs: Any,
    ) -> None:
        return super().place(
            x=x,
            y=y,
            relx=relx,
            rely=rely,
            width=width,
            height=height,
            relwidth=relwidth,
            relheight=relheight,
            anchor=anchor,
            **kwargs,
        )

    def coords(self, x: int | None = None, y: int | None = None, **kwargs: Any) -> "Image":
        return super().coords(x, y, **kwargs)

    def bind(self, sequence: str, func: Callable, add: str | None = None) -> str:
        if self._is_lifecycle_event(sequence):
            return self._bind_lifecycle_event(sequence, func, add)
        return self.canvas.tag_bind(self._image_id, sequence, func, add=add)

    def unbind(self, sequence: str, funcid: str | None = None) -> None:
        if self._is_lifecycle_event(sequence):
            self._unbind_lifecycle_event(sequence, funcid)
            return
        self.canvas.tag_unbind(self._image_id, sequence, funcid)

    def _hide(self) -> None:
        self._update_appearance_tracker()
        resume = self._video_is_playing
        if self._is_video:
            self._video_decode_pause.set()
            self.pause_video()
            self._video_resume_on_show = resume
        self.canvas.itemconfigure(self._image_id, state="hidden")

    def _show(self) -> None:
        self._update_appearance_tracker()
        self._video_decode_pause.clear()
        if self._render_deferred or (
            self._appearance_dependent()
            and ctk.get_appearance_mode() != self._last_rendered_appearance
        ):
            self._set_appearance_mode()
        self.canvas.itemconfigure(self._image_id, state="normal")
        if self._is_video and (
            self._video_resume_on_show or self._video_autoplay_pending
        ):
            self._video_autoplay_pending = False
            self._queue_video_autoplay()

    def _load_source(
        self,
        source: str | Path | PILImage.Image | ctk.CTkImage | None,
        video: bool | None = None,
    ) -> None:
        self._detach_ctk_image_callback()
        self.pause_video()
        self._close_video_reader()
        self.image = source
        self._video_requested = video
        self._source_image = None
        self._source_cache_key = None
        self._video_path = None
        self._video_needs_open = False
        self._video_resume_on_show = False
        self._video_autoplay_pending = False
        if isinstance(source, ctk.CTkImage) and video:
            raise ValueError("CTkImage cannot be used as a video source.")
        self._is_video = _is_video_source(self, source) if video is None else bool(video)

        if self._is_video:
            if source is None or isinstance(source, PILImage.Image):
                raise ValueError("Image video mode requires a video file path.")
            self._video_path = _resolve_path(self, source, VIDEO_EXTENSIONS, "Video resource")
            self._video_needs_open = True
            self._video_autoplay_pending = self.video_autoplay
            return
        if source is None:
            self._source_cache_key = ("empty",)
        elif isinstance(source, PILImage.Image):
            self._source_image = source.copy().convert("RGBA")
            self._source_cache_key = None
        elif isinstance(source, ctk.CTkImage):
            self._source_image = _resolve_image(self, source)
            self._source_cache_key = self._still_source_cache_key(source)
        else:
            path = _resolve_path(self, source, IMAGE_EXTENSIONS, "Image resource").resolve()
            stat = path.stat()
            self._source_image = _load_cached_image_file(
                str(path), stat.st_mtime_ns, stat.st_size
            )
            self._source_cache_key = (
                "path", str(path), stat.st_mtime_ns, stat.st_size
            )
        if isinstance(source, ctk.CTkImage):
            self._ctk_image_source = source
            source.add_configure_callback(self._ctk_image_changed)

    def _ensure_video_backend(self) -> None:
        if self._video_backend:
            return
        try:
            import imageio.v2 as imageio  # type: ignore

            self._video_backend = "imageio"
            self._video_reader = imageio
            return
        except Exception:
            pass
        raise RuntimeError(
            "Image video playback requires an optional decoder. "
            "Install imageio[ffmpeg]."
        )

    def _video_target_size(self) -> tuple[int, int]:
        padx_x, _ = _padding_pair(self.padx)
        pady_y, _ = _padding_pair(self.pady)
        return (
            max(1, int(round(self._apply_widget_scaling(self._width - padx_x * 2)))),
            max(1, int(round(self._apply_widget_scaling(self._height - pady_y * 2)))),
        )

    @staticmethod
    def _prepare_video_frame(frame: Any, target_size: tuple[int, int]) -> PILImage.Image:
        image = PILImage.fromarray(frame).convert("RGBA")
        if image.size != target_size:
            image = image.resize(target_size, PILImage.Resampling.BILINEAR)
        return image

    def _initialize_video_buffer(self, first_frame: PILImage.Image, total_frames: int) -> None:
        target_width, target_height = first_frame.size
        frame_bytes = max(1, target_width * target_height * 4)
        budget_bytes = max(frame_bytes * 2, int(self.video_cache_mb * 1024 * 1024))
        capacity = max(2, budget_bytes // frame_bytes)

        self._video_frame_queue = Queue(maxsize=capacity)
        self._video_decode_stop = threading.Event()
        self._video_decode_eof = threading.Event()
        self._video_cache_complete = threading.Event()
        self._video_full_cache = total_frames > 0 and total_frames <= capacity
        self._video_frame_cache = [first_frame] if self._video_full_cache else []
        self._video_cache_index = 0
        self._video_buffering = True
        self._source_image = first_frame
        self._update_video_preload_size()

    def _update_video_preload_size(self) -> None:
        if self._video_frame_queue is None:
            self._video_preload_frames = 1
            return
        requested = max(
            1,
            math.ceil(max(1.0, float(self.video_fps or 30)) * self.video_preload_seconds),
        )
        self._video_preload_frames = min(self._video_frame_queue.maxsize, requested)

    def _open_video(self) -> None:
        self._ensure_video_backend()
        self._close_video_reader()
        if self._video_path is None:
            return

        target_size = self._video_target_size()
        iterator = self._video_reader.get_reader(str(self._video_path))
        try:
            metadata = iterator.get_meta_data()
        except Exception:
            metadata = {}
        fps = float(metadata.get("fps") or 30)
        self._video_source_fps = fps if fps > 0 else 30.0
        self.video_fps = self._video_fps_override or self._video_source_fps
        raw_total = metadata.get("nframes", 0)
        try:
            total_frames = int(raw_total) if math.isfinite(float(raw_total)) else 0
        except (TypeError, ValueError, OverflowError):
            total_frames = 0
        try:
            first_frame = self._prepare_video_frame(iterator.get_next_data(), target_size)
        except Exception as exc:
            iterator.close()
            raise RuntimeError(f"Unable to decode video: {self._video_path}") from exc
        self._video_iterator = iterator
        self._initialize_video_buffer(first_frame, total_frames)
        decoder = iterator

        stop_event = self._video_decode_stop
        eof_event = self._video_decode_eof
        cache_complete = self._video_cache_complete
        frame_queue = self._video_frame_queue
        if stop_event is None or eof_event is None or cache_complete is None or frame_queue is None:
            return
        thread = threading.Thread(
            target=self._decode_video_frames,
            args=(
                decoder,
                target_size,
                frame_queue,
                stop_event,
                eof_event,
                cache_complete,
                self._video_full_cache,
                self._video_frame_cache,
            ),
            name=f"CanvasCTk-video-{id(self):x}",
            daemon=True,
        )
        self._video_decode_thread = thread
        thread.start()

    def _decode_video_frames(
        self,
        decoder: Any,
        target_size: tuple[int, int],
        frame_queue: Queue[PILImage.Image],
        stop_event: threading.Event,
        eof_event: threading.Event,
        cache_complete: threading.Event,
        full_cache: bool,
        frame_cache: list[PILImage.Image],
    ) -> None:
        try:
            while not stop_event.is_set():
                while self._video_decode_pause.is_set() and not stop_event.wait(0.05):
                    pass
                if stop_event.is_set():
                    return
                try:
                    raw_frame = decoder.get_next_data()
                    ok = True
                except Exception:
                    raw_frame = None
                    ok = False

                if not ok:
                    if full_cache:
                        cache_complete.set()
                        eof_event.set()
                        return
                    if not self.video_loop:
                        eof_event.set()
                        return
                    try:
                        decoder.set_image_index(0)
                    except Exception:
                        eof_event.set()
                        return
                    continue

                frame = self._prepare_video_frame(raw_frame, target_size)
                if full_cache:
                    frame_cache.append(frame)

                while not stop_event.is_set():
                    try:
                        frame_queue.put(frame, timeout=0.05)
                        break
                    except Full:
                        continue
        except Exception:
            if not stop_event.is_set():
                eof_event.set()

    def _close_video_reader(self) -> None:
        stop_event = self._video_decode_stop
        thread = self._video_decode_thread
        capture = self._video_capture
        iterator = self._video_iterator
        if stop_event is not None:
            stop_event.set()
        if thread is not None and thread is not threading.current_thread() and thread.is_alive():
            thread.join(timeout=1.0)
        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass
        if iterator is not None:
            try:
                iterator.close()
            except Exception:
                pass
        self._video_capture = None
        self._video_iterator = None
        self._video_decode_thread = None
        self._video_decode_stop = None
        self._video_decode_eof = None
        self._video_cache_complete = None
        self._video_frame_queue = None
        self._video_frame_cache = []
        self._video_cache_index = 0
        self._video_full_cache = False
        self._video_buffering = True

    def _read_video_frame(self) -> PILImage.Image | None:
        if self._video_frame_queue is not None:
            try:
                return self._video_frame_queue.get_nowait()
            except Empty:
                pass
        cache_complete = self._video_cache_complete
        if (
            self.video_loop
            and self._video_full_cache
            and cache_complete is not None
            and cache_complete.is_set()
            and self._video_frame_cache
        ):
            frame = self._video_frame_cache[self._video_cache_index]
            self._video_cache_index = (self._video_cache_index + 1) % len(self._video_frame_cache)
            return frame
        return None

    def _skip_video_frames(self, count: int) -> None:
        if count <= 0:
            return
        remaining = count
        if self._video_frame_queue is not None:
            while remaining > 0:
                try:
                    self._video_frame_queue.get_nowait()
                    remaining -= 1
                except Empty:
                    break
        cache_complete = self._video_cache_complete
        if (
            remaining > 0
            and self.video_loop
            and self._video_full_cache
            and cache_complete is not None
            and cache_complete.is_set()
            and self._video_frame_cache
        ):
            self._video_cache_index = (
                self._video_cache_index + remaining
            ) % len(self._video_frame_cache)

    def _video_buffer_ready(self) -> bool:
        cache_complete = self._video_cache_complete
        if self._video_full_cache and cache_complete is not None and cache_complete.is_set():
            return True
        eof_event = self._video_decode_eof
        if eof_event is not None and eof_event.is_set():
            return True
        if self._video_frame_queue is None:
            return False
        return self._video_frame_queue.qsize() >= self._video_preload_frames

    def _schedule_video_tick(self, delay: int) -> None:
        if self._video_is_playing and self._video_after_id is None:
            self._video_after_id = self.after(max(1, delay), self._video_tick)

    def _queue_video_autoplay(self) -> None:
        if self._video_autoplay_after_id is None:
            self._video_autoplay_after_id = self.after(0, self._autoplay_video)

    def _autoplay_video(self) -> None:
        self._video_autoplay_after_id = None
        if not self._is_rendered:
            self._video_autoplay_pending = True
            return
        if self._is_video and (self.video_autoplay or self._video_resume_on_show):
            self._video_resume_on_show = False
            self.play_video()

    def _video_tick(self) -> None:
        self._video_after_id = None
        if not self._video_is_playing:
            return
        if self._video_decode_pause.is_set():
            self._schedule_video_tick(50)
            return
        if self._video_buffering and not self._video_buffer_ready():
            self._schedule_video_tick(5)
            return

        frame = self._read_video_frame()
        if frame is None:
            eof_event = self._video_decode_eof
            if eof_event is not None and eof_event.is_set():
                self.pause_video()
                return
            self._video_buffering = True
            self._video_next_frame_at = None
            self._schedule_video_tick(5)
            return

        self._video_buffering = False
        target_time = self._video_next_frame_at or time.perf_counter()
        self._source_image = frame
        self._render()
        interval = 1 / max(1.0, float(self.video_fps or 30))
        next_frame_at = target_time + interval
        now = time.perf_counter()
        if now >= next_frame_at:
            skipped = int((now - next_frame_at) // interval) + 1
            self._skip_video_frames(skipped)
            next_frame_at += skipped * interval
        self._video_next_frame_at = next_frame_at
        delay = max(1, round((next_frame_at - now) * 1000))
        self._schedule_video_tick(delay)

    def play_video(self) -> None:
        if not self._is_video:
            return
        if not self._is_rendered:
            self._video_resume_on_show = True
            return
        if self._video_is_playing:
            return
        if self._video_needs_open or (
            self._video_capture is None and self._video_iterator is None
        ):
            self._open_video()
            self._video_needs_open = False
            self._render()
        self._video_is_playing = True
        self._video_next_frame_at = None
        self._video_buffering = not self._video_buffer_ready()
        if self._video_after_id is None:
            self._video_tick()

    def pause_video(self) -> None:
        self._video_is_playing = False
        self._video_resume_on_show = False
        self._video_next_frame_at = None
        if self._video_autoplay_after_id is not None:
            try:
                self.after_cancel(self._video_autoplay_after_id)
            except Exception:
                pass
            self._video_autoplay_after_id = None
        if self._video_after_id is not None:
            try:
                self.after_cancel(self._video_after_id)
            except Exception:
                pass
            self._video_after_id = None

    def restart_video(self) -> None:
        if not self._is_video:
            return
        self.pause_video()
        if not self._is_rendered:
            self._video_needs_open = True
            self._video_resume_on_show = True
            return
        self._open_video()
        self._video_needs_open = False
        self._render()
        self.play_video()

    def stop_video(self, clear: bool = True) -> None:
        self.pause_video()
        self._close_video_reader()
        if clear:
            self._source_image = None
            self._render()

    def destroy(self) -> None:
        self._detach_layout()
        if self._appearance_tracker_registered:
            AppearanceModeTracker.remove(self._set_appearance_mode)
            self._appearance_tracker_registered = False
        self._detach_ctk_image_callback()
        self.stop_video(clear=False)
        self._cleanup_canvas_element()
        self.canvas.delete(self._image_id)
        self._photo = None
        self._photo_is_shared = False


