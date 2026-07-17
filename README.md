# CanvasCTk

`CanvasCTk` is a standalone CustomTkinter canvas framework.

The public API now uses `Canvas*` names:

```python
from CanvasCTk import Window, Frame, Image, Text, Button, setup
```

## Install

```powershell
py -m pip install CanvasCTk
```

For local development:

```powershell
py -m pip install -e .
```

Install any missing project dependencies without reinstalling CanvasCTk:

```powershell
py -m pip install -r requirements.txt
py -m pip check
```

## Build and reinstall

Update `__version__` in `CanvasCTk/__init__.py`, then build the wheel and source archive:

```powershell
py -m pip install --upgrade build
py -m build
```

The build artifacts are written to `dist`. Reinstall a built wheel without reinstalling its dependencies:

```powershell
py -m pip install --force-reinstall --no-deps .\dist\CanvasCTk-<version>-py3-none-any.whl
```

Video support for `Image(image="video.mp4")` uses ffmpeg through `imageio[ffmpeg]` and is installed with the normal package dependencies.

## Run examples

```powershell
py examples\widgets.py
py examples\example2.py
py examples\example3.py
py examples\example4.py
py examples\example5.py
py examples\example6.py
```

`widgets.py` is the full widget showcase.

## Minimal app

`Window` no longer requires a window-config object. Pass the window settings directly:

```python
from CanvasCTk import Button, Window, setup


setup("Dark")

app = Window(
    title="My Canvas App",
    width=900,
    height=600,
    locked_width=False,
    locked_height=False,
    no_titlebar=False,
)

Button(app, text="Hello", command=lambda: print("Clicked")).pack(padx=24, pady=24)

app.center_window()
app.open()
```

## Backgrounds

Use `Image` directly for image backgrounds:

```python
from CanvasCTk import Frame, Image

scene = Frame(app, width=900, height=600, corner_radius=0)
scene.pack(fill="both", expand=True)

Image(
    scene,
    image="background.png",
    width=900,
    height=600,
    x=0,
    y=0,
    anchor="nw",
).show()
```

Glass/transparent panel:

```python
glass = Frame(scene, canvas=scene.canvas, fg_color="transparent")
glass.show()

Image(
    glass,
    x=80,
    y=80,
    width=520,
    height=260,
    anchor="nw",
    fg_color="#101827",
    opacity=0.55,
    border_radius=28,
    border_width=2,
    border_color="#8fd3ff",
).show()
```

Important transparency rule: use a shared canvas when you want true alpha blending:

```python
glass = Frame(scene, canvas=scene.canvas, fg_color="transparent")
glass.show()
```

Canvas items start hidden, like normal Tk widgets. After constructing a raw
coordinate-positioned `Image`, `Text`, `Button`, or logical `Frame`, call
`.show()`. Calling `.place()`, `.grid()`, or `.pack()` also shows the item.
As with Tk, `pack()` ignores constructor `x`/`y` coordinates; use `.show()` or
`.place()` when positioning by coordinates.

## Public widgets

Windows/dialogs:

- `Window`
- `Toplevel`
- `Dialog`
- `MessageBox`
- `show_canvas_messagebox(...)`

Containers:

- `Frame`
- `TabView`
- `ScrollableFrame`

Canvas-drawn items:

- `Text`
- `Image`
- `ImageButton`
- `Item`

CustomTkinter-backed controls:

- `Label`
- `Button`
- `Entry`
- `Checkbox`
- `RadioButton`
- `ProgressBar`
- `OptionMenu`
- `Textbox`

Base/helper exports:

- `Element`
- `ElementBase`
- `Widget`
- `ToolTip`
- `ThemeMode`
- `limit_scaling(...)`
- `setup(...)`

## Image

Use `Image` for normal images, generated color cards, transparent overlays, rounded panels, and optional video.

```python
Image(
    frame,
    image="logo.png",
    x=40,
    y=40,
    width=128,
    height=128,
    anchor="nw",
    opacity=0.8,
    brightness=1.1,
)
```

Color-only card:

```python
Image(
    frame,
    x=40,
    y=40,
    width=300,
    height=160,
    anchor="nw",
    fg_color="#111827",
    bg_opacity=0.55,
    border_radius=24,
    border_width=2,
    border_color="#8fd3ff",
)
```

Image with padded rounded backing:

```python
Image(
    frame,
    image="avatar.png",
    width=160,
    height=160,
    fg_color="#111827",
    bg_opacity=0.55,
    border_radius=28,
    padx=16,
    pady=16,
)
```

Video:

```python
video = Image(
    frame,
    image="example_vid.mp4",
    width=760,
    height=402,
    video_loop=True,
    video_autoplay=True,
)

video.pause_video()
video.play_video()
video.restart_video()
video.stop_video()
```

## ImageButton

`ImageButton` supports launcher-style visual states:

- normal
- hover
- selected
- disabled

The image is rendered as the button's visual background, with text layered over it. Each state can control backing and image opacity and brightness.

```python
button = ImageButton(
    frame,
    image="launch.png",
    size=(260, 72),
    text="Launch",
    width=260,
    height=72,
    fg_color="#24507a",
    hover_color="#326b9f",
    select_color="#7c3aed",
    bg_normal_opacity=0.55,
    bg_hover_opacity=0.85,
    bg_selected_opacity=0.95,
    bg_disabled_opacity=0.25,
    button_hover_brightness=1.2,
    border_radius=18,
    command=lambda: print("clicked"),
)

button.set_selected(True)
button.set_disabled(False)
button.set_state_style("hover", target="background", opacity=0.9)
```

## Inputs

`ScrollableDropdown` uses single-choice behavior by default. Enable multiple choices with `multiple_choice=True`:

```python
menu = ScrollableDropdown(
    parent,
    values={"fast": "Fast", "balanced": "Balanced", "quality": "High quality"},
    multiple_choice=True,
    command=lambda selected: print(selected),
)
menu.set(["fast", "quality"])
selected = menu.get()
```

In multiple-choice mode, selecting a row toggles it without closing the popup. `get()` and the command callback return a list. The closed button displays the selected labels separated by commas.

The closed button keeps its configured width in multiple-choice mode. When a Tk variable is supplied, selected values are stored as a Tcl list and are restored when the variable changes:

```python
selected_var = tk.StringVar(value="fast quality")
menu = ScrollableDropdown(
    parent,
    values=["fast", "balanced", "quality"],
    variable=selected_var,
    multiple_choice=True,
)
```

Enable the search bar with `search_bar=True`. It filters displayed labels while you type, and its prompt can be customized with `search_placeholder_text="Find an option..."`.

`Entry`:

```python
entry = Entry(parent, placeholder_text="Number", input_filter="FLOAT")
entry.set("123.45")
```

Filters:

- `input_filter="INT"`
- `input_filter="FLOAT"`

`Entry` and `Textbox` include:

- right-click menu
- cut/copy/paste/delete
- select all
- undo/redo

`Textbox` can sync with a Tk variable:

```python
text_var = tk.StringVar(value="Hello")
textbox = Textbox(parent, text_variable=text_var)
```

## Layout

Normal CustomTkinter-backed widgets use normal Tk layout:

```python
Button(parent, text="OK").pack()
Entry(parent).grid(row=0, column=0)
Label(parent, text="Hi").place(x=20, y=20)
```

Canvas-drawn items also expose `.place()`, `.grid()`, and `.pack()`, but these are logical canvas layouts:

```python
Text(frame, text="Title").place(x=40, y=40, anchor="nw")
ImageButton(frame, text="Tile").grid(row=0, column=0)
Text(frame, text="Bottom").pack(side="bottom", anchor="w", padx=20, pady=20)
```

## Tooltips

Every framework element can use:

```python
button.set_tooltip("Click to continue", delay=250)
```

Callable/refreshing tooltip:

```python
button.set_tooltip(lambda: f"Current value: {value.get()}", delay=250, refresh=500)
```

## Dialogs

```python
from CanvasCTk import MessageBox

response = MessageBox(
    app,
    title="Confirm",
    message="Do you want to continue?",
    buttons=("Cancel", "OK"),
).ask()
```

With checkbox options:

```python
response, options = Dialog(
    app,
    title="Options",
    message="Choose settings.",
    buttons=("No", "Yes"),
    checkbox_options=(("Remember", False),),
).ask_with_options()
```

## Theme and window helpers

```python
setup("Dark")
app.set_appearance("Light")
app.load_theme("my-theme.json")
app.reload_theme()
app.fit_to_screen(margin=40)
```

## Resource paths

`Window` accepts `resource_root`:

```python
app = Window(title="Assets", resource_root=Path(__file__).parent / "assets")
Image(frame, image="logo.png")
```

Relative image paths resolve under the nearest owner/resource root.

## Naming

The standalone framework uses `Canvas*` names throughout the public API:
`Window`, `Frame`, `Text`, `Image`, `Button`,
`Dialog`, and so on.

## License

This project is licensed under the MIT License. See the repository root `LICENSE` file.
