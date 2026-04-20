from __future__ import annotations

import os
import time
from datetime import datetime

import cv2

from webvisionkit import BrowserApp


SAVE_INTERVAL_SECONDS = max(0.0, float(os.getenv("SAVE_INTERVAL_SECONDS", "10") or "10"))


def on_frame(image, context):
    if SAVE_INTERVAL_SECONDS <= 0:
        return {
            "screenshot_capture": {
                "status": "disabled",
                "note": "SAVE_INTERVAL_SECONDS is 0, so screenshot writing is disabled.",
            }
        }

    now = time.monotonic()
    last_save_monotonic = float(context.state.get("last_save_monotonic", 0.0) or 0.0)
    if last_save_monotonic and now - last_save_monotonic < SAVE_INTERVAL_SECONDS:
        return {
            "screenshot_capture": {
                "status": "waiting",
                "next_save_in_seconds": round(SAVE_INTERVAL_SECONDS - (now - last_save_monotonic), 2),
            }
        }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = context.save_dir / f"screenshot_{timestamp}.jpg"
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"Failed to save image to {path}")

    context.state["last_save_monotonic"] = now
    print(f"[saved] {path}")
    return {
        "screenshot_capture": {
            "status": "saved",
            "path": str(path),
        }
    }


app = BrowserApp(
    start_target="game://input-lab",
    fps=1.0,
    on_frame=on_frame,
)
