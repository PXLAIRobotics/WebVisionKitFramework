# Framework Overview

## Mental Model

WebVisionKit is not DOM automation. Students do not search the page with selectors or depend on a site's internal HTML structure. Instead, an app receives rendered browser frames, reasons about those pixels, and acts through browser input primitives such as click, drag, scroll, and keyboard input.

That model is deliberate. It keeps the student problem focused on vision, state, and control instead of page-specific DOM details.

## Runtime Architecture

1. Google Chrome runs on the host with DevTools remote debugging enabled.
2. `./launch.bash` prepares Chrome, validates Docker connectivity, and launches the selected app.
3. The container runs the `webvisionkit` runtime package and the student app.
4. Chrome DevTools Protocol (CDP) delivers screencast frames into the runtime.
5. The app returns observations and browser actions, and the runtime forwards those actions back to Chrome.

## Where Student Code Lives

Student apps live under:

```text
apps/<name>/app.py
```

Each app must export:

```python
app = BrowserApp(...)
```

That keeps each project self-contained and easy to launch through `./launch.bash`.

## Targets You Can Use

WebVisionKit apps can start on:

- `about:blank`
- External URLs such as `https://example.com`
- Bundled `game://...` targets such as `game://input-lab` or `game://simple_drag`

Bundled `game://...` targets are resolved by the launcher before the container starts. They are a launcher feature, not a special browser action API.

## Frame Pixels vs Browser Viewport

`context.frame_width` and `context.frame_height` describe the delivered frame size that your app receives in `on_frame(...)`. Browser inputs are specified in that same frame-pixel space.

Internally, the runtime maps those frame pixels back to the browser's CSS viewport before dispatching input events. That means students can reason in the same coordinate system they see in the image, while the runtime handles the browser-space conversion.

## Browser Window Size vs Delivered Frame Size

Chrome itself is launched maximized by the launcher, so the visible browser window can be larger than the frame size your app sees. Screencast delivery is a separate step: WebVisionKit passes `MAX_WIDTH` and `MAX_HEIGHT` into the Chrome DevTools screencast request as maximum bounds for the delivered frame.

That is why a larger browser window can still produce a smaller delivered frame such as `1280x642`. The real viewport can be larger, but the screencast frame is scaled to fit within the configured max bounds while preserving its aspect ratio.

If you want the runtime to omit those caps, run with:

```bash
MAX_WIDTH=0 MAX_HEIGHT=0 APP_NAME=frame_report ./launch.bash
```

If you want a larger capped delivery size, run with:

```bash
MAX_WIDTH=1920 MAX_HEIGHT=1080 APP_NAME=frame_report ./launch.bash
```

This is adjustable today through launcher and runtime environment variables. It is not currently configurable through `BrowserApp(...)` or another public Python sizing API in `webvisionkit`.

## Bundled Reference Apps

The repo ships a few small reference apps that show real runtime usage:

- `frame_report`: minimal observation app for smoke runs and debugging
- `screenshot_capture`: periodic screenshot writer
- `simple_drag`: small CV example that drags a red block into a green goal
- `interaction_showcase`: broader browser-input demo for `game://input-lab`
