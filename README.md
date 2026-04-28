# WebVisionKit

WebVisionKit is a classroom-oriented framework for students who need to treat a browser as a vision-and-control problem instead of a Document Object Model (DOM) automation problem, where code works directly with the page's HTML structure.

In WebVisionKit, an app is the student-written program that receives screenshots of the rendered web page, decides what to do next, and uses the runtime action API to send browser inputs back to Chrome.

The supported runtime model is:

1. Google Chrome runs on the host with DevTools remote debugging enabled.
2. `./launch.bash` starts or reuses Chrome, validates Docker connectivity, and launches the selected app.
3. The `webvisionkit` runtime package and the student app run inside Docker.
4. The container receives screenshots of the rendered website through the Chrome DevTools Protocol (CDP), which is Chrome's debugging and control API.
5. The app sends actions through the WebVisionKit runtime API, which forwards them back to Chrome through the same CDP connection.

That architecture is deliberate. Students see pixels, reason about state, and act through browser input primitives. They do not depend on page selectors or site-specific DOM hooks tied to a site's internal HTML structure.

## Documentation

This root README is the repo overview. For the student-first documentation set, start with:

- [Student Docs](docs/README.md)
- [Framework Overview](docs/framework.md)
- [webvisionkit API](docs/api.md)
- [Practical Examples](docs/examples.md)
- [Troubleshooting](docs/troubleshooting.md)

## What This Is Good For

- Introductory OpenCV exercises where students need real image input.
- Tree and graph algorithm assignments that play small web games.
- Controlled browser interaction labs where students map detections to clicks, drags, scrolls, and key presses.
- Classroom environments where the browser should stay on the host, but student code should stay containerized.

The bundled `games/input-lab/` fixture is the primary calibration environment. It exposes pointer, click, drag, scroll, text, and keyboard tasks with CV-friendly markers before students move on to games or arbitrary external sites.

## Support Boundary

WebVisionKit supports:

- an image stream from a Chrome page target
- frame-by-frame Python callbacks inside Docker
- browser input primitives such as click, drag, scroll, and keyboard input
- local bundled games and arbitrary URLs

WebVisionKit does not promise:

- compatibility with login flows, anti-bot protections, or sites that actively resist automation
- DOM-level page understanding
- production-grade browser automation beyond the image-stream-plus-input model

## Prerequisites

### macOS

- Docker Desktop
- Google Chrome installed in `/Applications/Google Chrome.app`, or `CHROME_APP` set to another Chrome app bundle
- `curl`
- either `sha256sum` or `shasum`

### Linux

- Docker Engine or Docker Desktop
- Google Chrome or Chromium on `PATH`, or `CHROME_APP` set explicitly
- `curl`
- either `sha256sum` or `shasum`

### WSL

- WSL2
- Docker Desktop with WSL integration enabled
- Google Chrome installed on Windows, or Google Chrome/Chromium installed inside WSL when using `--chrome-backend linux`
- `powershell.exe`
- `wslpath`
- `curl`
- either `sha256sum` or `shasum`

WSL1 is not supported.

## Five-Minute Student Quickstart

Build the runtime image once:

```bash
./infrastructure/docker/build.bash
```

Run the environment check:

```bash
./launch.bash doctor
```

Start the full launcher:

```bash
./launch.bash
```

For a bounded smoke run instead of an interactive session:

```bash
./launch.bash smoke
```

## Launcher Commands

- `./launch.bash` or `./launch.bash up`
  Full flow: discover apps, resolve the target, ensure Chrome, and run Docker.
- `./launch.bash chrome`
  Start or reuse Chrome with remote debugging enabled.
- `./launch.bash doctor`
  Non-interactive prerequisite and connectivity check. It validates Docker access, Chrome discovery, curl, SHA-256 tool availability, WSL requirements, the host DevTools endpoint, and container-to-host DevTools reachability.
- `./launch.bash smoke`
  Non-interactive bounded validation. By default it runs:
  - `frame_report` against `game://input-lab`
  - `frame_report` against `https://example.com`
  - `interaction_showcase` against `game://input-lab` with `ACTION_MODE=dry-run`
- `./launch.bash container`
  Lower-level direct container run using the current environment variables.

## Student App Layout

Student projects live under:

```text
apps/<name>/
```

Each app folder must contain:

```text
apps/<name>/app.py
```

Each `app.py` must export:

```python
app = BrowserApp(...)
```

The folder may also contain helper modules and assets. For classroom work, the supported pattern is a small self-contained project folder rather than a single giant script.

Most algorithmic game-playing apps are expected to be authored by students in their own app folders; the public WebVisionKit repo only ships small reference examples such as `apps/simple_drag/`.

## BrowserApp API

The beginner-facing API remains intentionally small:

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

### `BrowserApp(...)`

- `start_target`: default launch target for the app
- `fps`: callback rate
- `on_frame(image, context)`: called for each delivered frame

Supported target formats:

- `https://example.com`
- `about:blank`
- `game://input-lab`
- `game://simple_drag`
- other bundled local game tokens such as `game://tic-tac-toe`

## Callback Context

Inside `on_frame(image, context)`, the context object exposes:

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

The callback may return `None` or a `dict`. Returned fields are merged into the per-frame metadata record.

## Browser Control API

`context.browser` exposes site-agnostic input primitives:

- `open(url)`
- `move(x, y)`
- `mouse_down(x, y)`
- `mouse_up(x, y)`
- `click(x, y)`
- `double_click(x, y)`
- `drag(x1, y1, x2, y2)`
- `scroll(x, y, delta_x=0, delta_y=...)`
- `key_down(key)`
- `key_up(key)`
- `key_press(key)`
- `type_text(text)`
- `pause(duration_ms)`

Coordinates are always in the same image pixel space the callback receives.

## Included Apps

- `apps/screenshot_capture/`
  Periodic screenshot writer.
- `apps/frame_report/`
  Minimal observation app for smoke runs and debugging.
- `apps/interaction_showcase/`
  Framework browser-input demo for exercising the input-lab fixture and validating action execution paths.
- `apps/simple_drag/`
  Minimal color-detection example that drags a red block into a green goal with one high-level action call.

## Bundled Games

Bundled local targets live under `games/`:

- `game://input-lab`
- `game://simple_drag`
- `game://tic-tac-toe`
- `game://connect-4`
- `game://snake`
- `game://memory-match`
- `game://2048`

`game://input-lab` is the recommended first assignment target.

`game://simple_drag` is the smallest bundled drag example for learning the app API end to end.

Example launch command:

```bash
APP_NAME=simple_drag TARGET_URL_OVERRIDE=game://simple_drag ./launch.bash
```

## Useful Environment Variables

### Launcher

- `IMAGE_NAME`
- `APP_NAME`
- `TARGET_URL_OVERRIDE`
- `OUTPUT_DIR`
- `SCREENSHOT_DIR`
- `FORCE_REBUILD=1`
- `SMOKE_EXTERNAL_URL`

`OUTPUT_DIR` defaults to the repo-relative `./output` folder, not the caller’s current shell directory.

### Chrome

- `CHROME_APP`
- `WSL_CHROME_BACKEND=auto|linux|windows`
- `CHROME_PORT`
- `CHROME_PROFILE_DIR`
- `CHROME_REMOTE_ALLOW_ORIGINS`

On WSL, the default Chrome profile directory is a Windows-native path under `LocalApplicationData\WebVisionKit\chrome-cdp-profile`.
If Windows Chrome launch is unavailable, the launcher falls back to Linux Chrome in WSL and uses `/tmp/webvisionkit-chrome-cdp-profile` by default.
Use `./launch.bash --chrome-backend linux` or `./launch.bash doctor --chrome-backend linux` to require Chrome/Chromium inside WSL instead of native Windows Chrome.
Use `--chrome-backend windows` to require native Windows Chrome, or `--chrome-backend auto` for the default Windows-first behavior.

### Runtime

- `RECONNECT_ATTEMPTS`
- `RECONNECT_DELAY_SECONDS`
- `RECEIVE_TIMEOUT_SECONDS`
- `IDLE_TIMEOUT_SECONDS`
- `LOG_INTERVAL_SECONDS`
- `MAX_FRAMES`
- `LIVE_PREVIEW`
- `VIDEO_OUTPUT`
- `METADATA_OUTPUT`
- `PROCESSORS`

### Action Execution

- `ACTION_MODE=auto|dry-run|off`
- `ACTION_DEFAULT_COOLDOWN_MS`
- `ACTION_MAX_PER_FRAME`
- `ACTION_DRAG_STEP_COUNT`
- `ACTION_DRAG_STEP_DELAY_MS`

## Local Checks

Run non-mutating repository checks:

```bash
./scripts/check-env.sh
```

Run the unit-test suite:

```bash
./scripts/test.sh
```

The test suite covers:

- launcher target resolution
- websocket host rewriting
- config parsing
- action validation and cooldown handling
- app discovery and helper-module imports inside `apps/<name>/`

## Troubleshooting

### `./launch.bash doctor` fails before Docker starts

- Start Docker Desktop or the Docker daemon.
- Confirm `docker info` works for your user.
- Confirm `curl` exists on the host.
- Install either `sha256sum` or `shasum`.

### Chrome is not discovered

- macOS: set `CHROME_APP` if Chrome is not in `/Applications/Google Chrome.app`
- Linux: set `CHROME_APP` to the Chrome or Chromium executable
- WSL: set `CHROME_APP` to the Windows `chrome.exe` path if Chrome is not in the default location, or run `./launch.bash --chrome-backend linux` to use Chrome/Chromium inside WSL

### The container cannot reach `host.docker.internal`

- macOS and Docker Desktop: the default hostname should work
- Native Linux: WebVisionKit adds `--add-host=host.docker.internal:host-gateway` automatically
- WSL2: use Docker Desktop with WSL integration enabled

### WSL launches Chrome but the endpoint never appears

- Confirm you are on WSL2, not WSL1
- Confirm Windows interop works by running a simple `powershell.exe -NoProfile -Command "Write-Output ok"` from WSL
- If Windows interop fails, install Linux Chrome/Chromium in WSL so launcher fallback can be used
- If Linux Chrome is missing in WSL fallback mode, the launcher auto-installs Google Chrome using:
  `wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb`
- Check Windows Chrome startup manually with the same remote debugging port when using the Windows backend
- Re-run `./launch.bash doctor` to verify the host endpoint and the container probe separately

### WSL Linux fallback launches Chrome but container cannot connect

- The launcher tries container reachability in this order when Linux fallback mode is used: WSL gateway first, then `host.docker.internal`
- It automatically selects the first reachable candidate for `CHROME_HOST_IN_CONTAINER`
- If your setup uses a different route, set `CHROME_HOST_IN_CONTAINER` explicitly before launch
- Re-run `./launch.bash doctor` and check the logged "Effective CHROME_HOST_IN_CONTAINER"

### Output files are owned by root

On native Linux and WSL, WebVisionKit runs the container with the calling user’s UID and GID by default so output files stay user-owned. If you override container args manually, avoid removing that behavior unless you want root-owned artifacts.
