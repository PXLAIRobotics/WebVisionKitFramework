# webvisionkit API

## Minimal Public Surface

At the top level, the `webvisionkit` package exports:

- `BrowserApp`
- `BrowserActions`

That small surface is intentional. Most student work happens inside `on_frame(...)`, `context.browser`, and `context.stream`.

## BrowserApp

```python
from webvisionkit import BrowserApp

def on_frame(image, context):
    return {}

app = BrowserApp(
    start_target="about:blank",
    fps=1.0,
    on_frame=on_frame,
)
```

- `start_target`: the default launch target for the app
- `fps`: the callback rate for `on_frame(...)`
- `on_frame(image, context)`: the function called for each delivered frame

## on_frame Contract

- `image` is the current frame image delivered by the runtime
- `context` is the runtime state and control object for the callback
- The callback may return `None` or a `dict`
- If you return a `dict`, its fields are merged into the per-frame metadata record

## Context Object

Inside `on_frame(...)`, the context object exposes:

- `context.state`
- `context.browser`
- `context.stream`
- `context.frame_index`
- `context.session_index`
- `context.url`
- `context.frame_width`
- `context.frame_height`
- `context.save_dir`
- `context.captured_at`
- `context.recent_action_results`

## context.browser Methods

`context.browser` exposes these methods:

- `open(url, *, name=None, reason=None)`
- `move(x, y, **kwargs)`
- `mouse_down(x=None, y=None, **kwargs)`
- `mouse_up(x=None, y=None, **kwargs)`
- `click(x, y, **kwargs)`
- `double_click(x, y, **kwargs)`
- `drag(x, y, end_x, end_y, **kwargs)`
- `scroll(x, y, delta_x=0, delta_y=0, **kwargs)`
- `key_down(key, **kwargs)`
- `key_up(key, **kwargs)`
- `key_press(key, **kwargs)`
- `type_text(text, **kwargs)`
- `pause(duration_ms, **kwargs)`

These methods create browser actions in frame-pixel coordinates. `open(...)` is the exception: it queues a URL navigation request instead of a pointer or keyboard action.

## Common Action Fields

Most `context.browser` methods accept additional keyword fields that become part of the action:

- `name`: a stable label for the action
- `reason`: a short explanation of why the action was queued
- `cooldown_ms`: minimum delay before the same named action is allowed again
- `modifiers`: keyboard modifiers such as Shift, Ctrl, Alt, or Meta
- `button`: mouse button for click-related actions
- `delta_x`: horizontal scroll delta for `scroll(...)`
- `delta_y`: vertical scroll delta for `scroll(...)`

## context.stream

`context.stream` controls the callback rate:

- `set_fps(fps)`: update the callback FPS for later frames
- `get_fps()`: read the current callback FPS

This is useful when you want to search quickly, then slow down after finding a stable state.

## BrowserActions (Advanced)

`BrowserActions` builds explicit action dictionaries. This is useful when you want to name actions, apply cooldowns, or construct actions before deciding whether to queue them.

Example:

```python
from webvisionkit import BrowserActions

action = BrowserActions.click(320, 180, name="center-click", cooldown_ms=500)
context.browser.queue_action(action)
```

More examples:

```python
from webvisionkit import BrowserActions

click_action = BrowserActions.click(320, 180, name="primary-click")
drag_action = BrowserActions.drag(120, 200, 460, 200, name="drag-piece")
scroll_action = BrowserActions.scroll(640, 360, delta_y=450, name="page-scroll")
key_action = BrowserActions.key_press("Enter", name="submit")
text_action = BrowserActions.type_text("Hello from WebVisionKit", name="type-message")
pause_action = BrowserActions.pause(250, name="short-wait")

context.browser.queue_action(click_action)
context.browser.queue_action(drag_action)
context.browser.queue_action(scroll_action)
context.browser.queue_action(key_action)
context.browser.queue_action(text_action)
context.browser.queue_action(pause_action)
```

## Coordinate Rules

Coordinates must already be in frame pixels. There is no supported `coordinate_space` override in the public action model.

Coordinates must also stay within:

- `0 <= x <= context.frame_width`
- `0 <= y <= context.frame_height`

If an action uses coordinates outside the current frame, the runtime rejects it as invalid instead of dispatching it.

## Resolution and Capture Size

`context.frame_width` and `context.frame_height` describe the delivered screencast frame size, not the outer Chrome window size. Chrome is launched maximized by the launcher, but the runtime separately requests screencast frames with `MAX_WIDTH` and `MAX_HEIGHT` as maximum bounds.

That is why you can see a larger browser window while the app receives a frame such as `1280x642`. The viewport can be larger, but the delivered frame is scaled to fit within those screencast bounds while preserving aspect ratio.

To increase the cap:

```bash
MAX_WIDTH=1920 MAX_HEIGHT=1080 APP_NAME=frame_report ./launch.bash
```

To omit the cap entirely:

```bash
MAX_WIDTH=0 MAX_HEIGHT=0 APP_NAME=frame_report ./launch.bash
```

There is no current public Python API in `webvisionkit` that sets capture size directly.

## What This API Does Not Do

- It does not provide DOM selectors or DOM-level page understanding.
- It does not guarantee support for login flows, anti-bot protections, or hostile sites.
- It does not provide a `BrowserApp(...)` parameter for viewport or capture sizing today.
