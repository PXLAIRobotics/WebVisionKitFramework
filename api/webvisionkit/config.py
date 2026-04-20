from __future__ import annotations

import argparse
import math
import os
from typing import List, Optional, Sequence

from .models import DEFAULT_APPS_DIR, DEFAULT_SAVE_DIR, StreamConfig


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_processors(raw: str) -> List[str]:
    values = [value.strip().lower() for value in raw.split(",")]
    return [value for value in values if value and value != "none"]


def default_apps_dir() -> str:
    configured = os.getenv("APPS_DIR")
    if configured is not None and configured.strip():
        return configured.strip()
    return DEFAULT_APPS_DIR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a containerized WebVisionKit BrowserApp against an external Chrome DevTools endpoint.",
    )
    parser.add_argument("--chrome-host", default=os.getenv("CHROME_HOST", "host.docker.internal"))
    parser.add_argument("--chrome-port", type=int, default=int(os.getenv("CHROME_PORT", "9222")))
    parser.add_argument("--browser-browser-ws-url", default=os.getenv("BROWSER_BROWSER_WS_URL", "").strip())
    parser.add_argument("--browser-ws-url", default=os.getenv("BROWSER_WS_URL", "").strip())
    parser.add_argument("--apps-dir", default=default_apps_dir())
    parser.add_argument("--app-name", default=os.getenv("APP_NAME", "").strip())
    parser.add_argument("--app-default-target-url", default=os.getenv("APP_DEFAULT_TARGET_URL", "").strip())
    parser.add_argument("--target-url-override", default=os.getenv("TARGET_URL_OVERRIDE", "").strip())
    parser.add_argument("--target-match", default=os.getenv("TARGET_MATCH", "").strip().lower())
    parser.add_argument(
        "--target-close-action",
        choices=["exit", "reopen-last-url"],
        default=os.getenv("TARGET_CLOSE_ACTION", "exit").strip().lower() or "exit",
    )
    parser.add_argument(
        "--startup-target-mode",
        choices=["auto", "new-target"],
        default=os.getenv("STARTUP_TARGET_MODE", "new-target").strip().lower() or "new-target",
    )
    parser.add_argument("--frame-format", default=os.getenv("FRAME_FORMAT", "jpeg"))
    parser.add_argument("--frame-quality", type=int, default=int(os.getenv("FRAME_QUALITY", "70")))
    parser.add_argument("--every-nth-frame", type=int, default=int(os.getenv("EVERY_NTH_FRAME", "1")))
    parser.add_argument("--max-width", type=int, default=int(os.getenv("MAX_WIDTH", "1280")))
    parser.add_argument("--max-height", type=int, default=int(os.getenv("MAX_HEIGHT", "720")))
    parser.add_argument("--save-dir", default=os.getenv("SAVE_DIR", DEFAULT_SAVE_DIR).strip())
    parser.add_argument(
        "--save-interval-seconds",
        type=float,
        default=float(os.getenv("SAVE_INTERVAL_SECONDS", "10")),
    )
    parser.add_argument("--video-output", default=os.getenv("VIDEO_OUTPUT", "").strip())
    parser.add_argument("--metadata-output", default=os.getenv("METADATA_OUTPUT", "").strip())
    parser.add_argument("--processors", default=os.getenv("PROCESSORS", "").strip())
    parser.add_argument(
        "--reconnect-attempts",
        type=int,
        default=int(os.getenv("RECONNECT_ATTEMPTS", "10")),
        help="Use 0 for unlimited retries.",
    )
    parser.add_argument(
        "--reconnect-delay-seconds",
        type=float,
        default=float(os.getenv("RECONNECT_DELAY_SECONDS", "2")),
    )
    parser.add_argument(
        "--receive-timeout-seconds",
        type=float,
        default=float(os.getenv("RECEIVE_TIMEOUT_SECONDS", "5")),
    )
    parser.add_argument(
        "--idle-timeout-seconds",
        type=float,
        default=float(os.getenv("IDLE_TIMEOUT_SECONDS", "20")),
    )
    parser.add_argument(
        "--log-interval-seconds",
        type=float,
        default=float(os.getenv("LOG_INTERVAL_SECONDS", "1")),
    )
    parser.add_argument("--video-fps", type=float, default=float(os.getenv("VIDEO_FPS", "12")))
    parser.add_argument("--max-frames", type=int, default=int(os.getenv("MAX_FRAMES", "0")))
    parser.add_argument(
        "--action-mode",
        choices=["auto", "dry-run", "off"],
        default=os.getenv("ACTION_MODE", "auto").strip().lower() or "auto",
    )
    parser.add_argument(
        "--action-default-cooldown-ms",
        type=int,
        default=int(os.getenv("ACTION_DEFAULT_COOLDOWN_MS", "250")),
    )
    parser.add_argument(
        "--action-max-per-frame",
        type=int,
        default=int(os.getenv("ACTION_MAX_PER_FRAME", "0")),
        help="Use 0 for unlimited queued browser actions per callback.",
    )
    parser.add_argument(
        "--action-drag-step-count",
        type=int,
        default=int(os.getenv("ACTION_DRAG_STEP_COUNT", "8")),
    )
    parser.add_argument(
        "--action-drag-step-delay-ms",
        type=int,
        default=int(os.getenv("ACTION_DRAG_STEP_DELAY_MS", "16")),
    )

    default_live_preview = env_bool("LIVE_PREVIEW", False)
    parser.add_argument(
        "--live-preview",
        dest="live_preview",
        action="store_true",
        default=default_live_preview,
    )
    parser.add_argument(
        "--no-live-preview",
        dest="live_preview",
        action="store_false",
    )
    return parser


def parse_args(argv: Optional[Sequence[str]] = None) -> StreamConfig:
    args = build_parser().parse_args(argv)
    return StreamConfig(
        chrome_host=args.chrome_host,
        chrome_port=args.chrome_port,
        browser_browser_ws_url=args.browser_browser_ws_url,
        browser_ws_url=args.browser_ws_url,
        apps_dir=args.apps_dir,
        app_name=args.app_name,
        app_default_target_url=args.app_default_target_url,
        target_url_override=args.target_url_override,
        start_target_url="",
        target_match=args.target_match,
        target_close_action=args.target_close_action,
        startup_target_mode=args.startup_target_mode,
        frame_format=args.frame_format,
        frame_quality=args.frame_quality,
        every_nth_frame=max(1, args.every_nth_frame),
        max_width=max(0, args.max_width),
        max_height=max(0, args.max_height),
        save_dir=args.save_dir,
        save_interval_seconds=args.save_interval_seconds,
        live_preview=args.live_preview,
        video_output=args.video_output,
        metadata_output=args.metadata_output,
        processors=parse_processors(args.processors),
        reconnect_attempts=args.reconnect_attempts,
        reconnect_delay_seconds=max(0.1, args.reconnect_delay_seconds),
        receive_timeout_seconds=max(0.1, args.receive_timeout_seconds),
        idle_timeout_seconds=max(0.1, args.idle_timeout_seconds),
        log_interval_seconds=max(0.0, args.log_interval_seconds),
        video_fps=max(0.1, args.video_fps),
        max_frames=max(0, args.max_frames),
        action_mode=args.action_mode,
        action_default_cooldown_ms=max(0, args.action_default_cooldown_ms),
        action_max_per_frame=max(0, args.action_max_per_frame),
        action_drag_step_count=max(1, args.action_drag_step_count),
        action_drag_step_delay_ms=max(0, args.action_drag_step_delay_ms),
    )


def validate_positive_fps(value: float) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError("fps must be a positive finite number.")
    return number
