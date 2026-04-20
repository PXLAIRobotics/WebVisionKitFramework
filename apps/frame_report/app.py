from __future__ import annotations

import numpy as np

from webvisionkit import BrowserApp


def on_frame(image, context):
    mean_bgr = image.mean(axis=(0, 1))
    return {
        "frame_report": {
            "status": "observing",
            "mean_b": round(float(mean_bgr[0]), 2),
            "mean_g": round(float(mean_bgr[1]), 2),
            "mean_r": round(float(mean_bgr[2]), 2),
            "url": context.url,
            "frame_index": context.frame_index,
        }
    }


app = BrowserApp(
    start_target="about:blank",
    fps=2.0,
    on_frame=on_frame,
)
