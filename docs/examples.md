# Practical Examples

All examples below are regular `apps/<name>/app.py` files. Copy one into a new app folder, then launch it with `./launch.bash`.

When a section points to `APP_NAME=frame_report` or `APP_NAME=screenshot_capture`, that command runs the bundled reference app so you can see the pattern immediately. For the other sections, the launch command assumes you saved the snippet under the same app folder name used in the command.

## Example 1: Observe Frames

This mirrors the bundled `frame_report` idea. It teaches the basic callback shape and shows that you can inspect the image, the current URL, and frame counters without taking any actions.

```python
from webvisionkit import BrowserApp


def on_frame(image, context):
    return {
        "observer": {
            "frame_index": context.frame_index,
            "url": context.url,
            "mean_brightness": round(float(image.mean()), 2),
        }
    }


app = BrowserApp(
    start_target="game://input-lab",
    fps=2.0,
    on_frame=on_frame,
)
```

Try the bundled reference app:

```bash
APP_NAME=frame_report TARGET_URL_OVERRIDE=game://input-lab ./launch.bash
```

## Example 2: Save a Screenshot Every Few Seconds

This example shows how to write frames into `context.save_dir`. It uses `SAVE_INTERVAL_SECONDS` to avoid saving every frame.

```python
import os
import time
from datetime import datetime

from webvisionkit import BrowserApp
from webvisionkit.deps import cv2


SAVE_INTERVAL_SECONDS = max(0.0, float(os.getenv("SAVE_INTERVAL_SECONDS", "2") or "2"))


def on_frame(image, context):
    last_save = float(context.state.get("last_save", 0.0) or 0.0)
    now = time.monotonic()
    if last_save and now - last_save < SAVE_INTERVAL_SECONDS:
        return {"capture": {"status": "waiting"}}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = context.save_dir / f"student_capture_{timestamp}.jpg"
    if cv2 is None or not cv2.imwrite(str(path), image):
        raise RuntimeError(f"Failed to save screenshot to {path}")

    context.state["last_save"] = now
    return {"capture": {"status": "saved", "path": str(path)}}


app = BrowserApp(
    start_target="game://input-lab",
    fps=1.0,
    on_frame=on_frame,
)
```

Try the bundled reference app:

```bash
SAVE_INTERVAL_SECONDS=2 APP_NAME=screenshot_capture TARGET_URL_OVERRIDE=game://input-lab ./launch.bash
```

## Example 3: Use context.state to Click Only Once

`context.state` is persistent across frames for the running app. This example clicks the center of the frame once, records that it already acted, and avoids repeating the click on later frames.

```python
from webvisionkit import BrowserApp


def on_frame(image, context):
    if context.state.get("clicked"):
        return {"single_click": {"status": "already_clicked"}}

    center_x = context.frame_width // 2
    center_y = context.frame_height // 2
    context.browser.click(center_x, center_y, name="center-click")
    context.state["clicked"] = True

    return {
        "single_click": {
            "status": "queued",
            "x": center_x,
            "y": center_y,
        }
    }


app = BrowserApp(
    start_target="game://input-lab",
    fps=2.0,
    on_frame=on_frame,
)
```

If saved as `apps/my_single_click/app.py`, launch:

```bash
APP_NAME=my_single_click TARGET_URL_OVERRIDE=game://input-lab ./launch.bash
```

## Example 4: Open a New URL

This example shows `context.browser.open(...)`. Use it for normal URLs such as `https://example.com` or `about:blank`. Do not use it for `game://...` tokens, because those must be resolved by the launcher before the container starts.

```python
from webvisionkit import BrowserApp


def on_frame(image, context):
    if context.state.get("opened"):
        return {"open_url": {"status": "already_opened", "url": context.url}}

    context.browser.open(
        "https://example.com",
        name="open-example",
        reason="Show how browser.open queues navigation.",
    )
    context.state["opened"] = True
    return {"open_url": {"status": "queued", "target": "https://example.com"}}


app = BrowserApp(
    start_target="about:blank",
    fps=1.0,
    on_frame=on_frame,
)
```

If saved as `apps/my_open_url/app.py`, launch:

```bash
APP_NAME=my_open_url ./launch.bash
```

## Example 5: Type Text and Press Enter

`game://input-lab` is the safest place to practice text and keyboard input. This example clicks a known point, types text, and then presses Enter on the next frame.

```python
from webvisionkit import BrowserApp


TEXT_FIELD_X = 330
TEXT_FIELD_Y = 250


def on_frame(image, context):
    phase = context.state.get("phase", "focus")
    if phase == "focus":
        context.browser.click(TEXT_FIELD_X, TEXT_FIELD_Y, name="focus-text-field")
        context.state["phase"] = "type"
        return {"text_demo": {"status": "focused"}}

    if phase == "type":
        context.browser.type_text("Hello from WebVisionKit", name="type-text")
        context.browser.key_press("Enter", name="submit-text")
        context.state["phase"] = "done"
        return {"text_demo": {"status": "typed"}}

    return {"text_demo": {"status": "done"}}


app = BrowserApp(
    start_target="game://input-lab",
    fps=1.0,
    on_frame=on_frame,
)
```

If saved as `apps/my_text_demo/app.py`, launch:

```bash
APP_NAME=my_text_demo TARGET_URL_OVERRIDE=game://input-lab ./launch.bash
```

## Example 6: Change FPS Dynamically

This pattern is useful when you want to search quickly at first, then slow down after you have reached a stable state.

```python
from webvisionkit import BrowserApp


def on_frame(image, context):
    if not context.state.get("slowed_down") and context.frame_index >= 10:
        context.stream.set_fps(1.0)
        context.state["slowed_down"] = True
        return {"fps_demo": {"status": "slowed", "fps": context.stream.get_fps()}}

    return {"fps_demo": {"status": "searching", "fps": context.stream.get_fps()}}


app = BrowserApp(
    start_target="game://input-lab",
    fps=6.0,
    on_frame=on_frame,
)
```

If saved as `apps/my_fps_demo/app.py`, launch:

```bash
APP_NAME=my_fps_demo TARGET_URL_OVERRIDE=game://input-lab ./launch.bash
```

## Example 7: Build a Named Action With BrowserActions

`BrowserActions` lets you build an action dictionary yourself, attach a stable name, and add a cooldown. That is useful when you want more explicit control over what gets queued.

```python
from webvisionkit import BrowserApp, BrowserActions


def on_frame(image, context):
    if context.state.get("queued"):
        return {"named_action": {"status": "already_queued"}}

    action = BrowserActions.click(320, 180, name="center-click", cooldown_ms=500)
    context.browser.queue_action(action)
    context.state["queued"] = True

    return {"named_action": {"status": "queued", "action_name": "center-click"}}


app = BrowserApp(
    start_target="game://input-lab",
    fps=2.0,
    on_frame=on_frame,
)
```

If saved as `apps/my_named_action/app.py`, launch:

```bash
APP_NAME=my_named_action TARGET_URL_OVERRIDE=game://input-lab ./launch.bash
```

## Example 8: Drag One Detected Object to Another

This small CV example is inspired by `apps/simple_drag`. It finds a red block and a green goal, computes their centers, and queues a drag. Because it uses `cv2` and `numpy`, run it through `./launch.bash`.

```python
from webvisionkit import BrowserApp
from webvisionkit.deps import cv2, np


def find_center(mask):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < 300:
        return None
    x, y, w, h = cv2.boundingRect(contour)
    return (x + w // 2, y + h // 2)


def on_frame(image, context):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    red_mask = cv2.inRange(hsv, np.array([0, 120, 120]), np.array([10, 255, 255]))
    green_mask = cv2.inRange(hsv, np.array([45, 80, 80]), np.array([85, 255, 255]))

    block = find_center(red_mask)
    goal = find_center(green_mask)
    if block is None or goal is None:
        return {"drag_demo": {"status": "waiting_for_scene"}}

    if context.state.get("dragged"):
        return {"drag_demo": {"status": "already_dragged"}}

    context.browser.drag(block[0], block[1], goal[0], goal[1], name="drag-block-to-goal")
    context.state["dragged"] = True
    return {"drag_demo": {"status": "queued", "block": block, "goal": goal}}


app = BrowserApp(
    start_target="game://simple_drag",
    fps=2.0,
    on_frame=on_frame,
)
```

If saved as `apps/my_drag_demo/app.py`, launch:

```bash
APP_NAME=my_drag_demo TARGET_URL_OVERRIDE=game://simple_drag ./launch.bash
```

## Example 9: Read Recent Action Results

This example inspects `context.recent_action_results` so the app can react to the latest status of a named action instead of guessing whether it worked.

```python
from webvisionkit import BrowserApp


def latest_result(results, name):
    for item in reversed(results):
        if item.get("name") == name:
            return item
    return None


def on_frame(image, context):
    result = latest_result(context.recent_action_results, "center-click")
    if result is not None:
        return {"result_demo": {"status": "seen_result", "result": dict(result)}}

    if not context.state.get("queued"):
        context.browser.click(320, 180, name="center-click")
        context.state["queued"] = True
        return {"result_demo": {"status": "queued"}}

    return {"result_demo": {"status": "waiting_for_result"}}


app = BrowserApp(
    start_target="game://input-lab",
    fps=2.0,
    on_frame=on_frame,
)
```

If saved as `apps/my_result_demo/app.py`, launch:

```bash
APP_NAME=my_result_demo TARGET_URL_OVERRIDE=game://input-lab ./launch.bash
```
