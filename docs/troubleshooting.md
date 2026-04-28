# Troubleshooting

## Chrome Window Looks Bigger Than The Reported Frame

This is expected. Chrome is launched maximized by the launcher, but the delivered screencast frame is controlled separately by `MAX_WIDTH` and `MAX_HEIGHT`.

That means the outer browser window can look larger while your app receives a frame such as `1280x642`. The larger viewport is scaled to fit inside the screencast max bounds while preserving aspect ratio.

To raise the cap:

```bash
MAX_WIDTH=1920 MAX_HEIGHT=1080 APP_NAME=frame_report ./launch.bash
```

To omit the cap:

```bash
MAX_WIDTH=0 MAX_HEIGHT=0 APP_NAME=frame_report ./launch.bash
```

## My Click Coordinates Are Rejected

Pointer actions use the current frame's pixel space. Keep coordinates inside `context.frame_width` and `context.frame_height`.

If you click outside that range, the runtime rejects the action as invalid instead of dispatching it.

## My App Needs cv2 or numpy

Run student apps through `./launch.bash` so the container provides the expected runtime dependencies.

For CV-heavy examples, prefer:

```python
from webvisionkit.deps import cv2, np
```

## The Container Cannot Reach Chrome

Start with:

```bash
./launch.bash doctor
```

That checks Docker access, Chrome discovery, the host DevTools endpoint, and whether the container can reach Chrome from inside Docker.

If the failure is route-related, re-run `./launch.bash doctor` and inspect the reported host and container connectivity details before changing anything else.

## I Want To Practice Inputs Safely

Use `game://input-lab`. It is the recommended calibration environment for pointer, click, drag, scroll, text, and keyboard tasks.

## My Action Keeps Repeating

Use `context.state` to remember what your app already did, or give repeated actions a `name` plus `cooldown_ms` so the runtime can suppress rapid repeats.

## I Need To See What Is Possible

Read [Practical Examples](examples.md) and inspect the bundled reference apps:

- `apps/frame_report`
- `apps/screenshot_capture`
- `apps/simple_drag`
- `apps/interaction_showcase`
