from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
API_DIR = ROOT_DIR / "api"

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from webvisionkit.models import StreamConfig, TargetState  # noqa: E402


def make_stream_config(**overrides: object) -> StreamConfig:
    values = {
        "chrome_host": "host.docker.internal",
        "chrome_port": 9222,
        "browser_browser_ws_url": "",
        "browser_ws_url": "",
        "apps_dir": str(ROOT_DIR / "apps"),
        "app_name": "",
        "app_default_target_url": "",
        "target_url_override": "",
        "start_target_url": "about:blank",
        "target_match": "",
        "target_close_action": "exit",
        "startup_target_mode": "new-target",
        "frame_format": "jpeg",
        "frame_quality": 70,
        "every_nth_frame": 1,
        "max_width": 1280,
        "max_height": 720,
        "save_dir": "/tmp/output",
        "save_interval_seconds": 0.0,
        "live_preview": False,
        "video_output": "",
        "metadata_output": "",
        "processors": [],
        "reconnect_attempts": 1,
        "reconnect_delay_seconds": 1.0,
        "receive_timeout_seconds": 1.0,
        "idle_timeout_seconds": 5.0,
        "log_interval_seconds": 0.0,
        "video_fps": 12.0,
        "max_frames": 0,
        "action_mode": "dry-run",
        "action_default_cooldown_ms": 250,
        "action_max_per_frame": 0,
        "action_drag_step_count": 8,
        "action_drag_step_delay_ms": 16,
    }
    values.update(overrides)
    return StreamConfig(**values)


def make_target_state() -> TargetState:
    return TargetState(
        browser_ws_url="ws://host.docker.internal:9222/devtools/browser/abc",
        initial_page_ws_url="",
        initial_page_ws_url_valid=False,
        startup_target_pending=False,
        current_page_ws_url="ws://host.docker.internal:9222/devtools/page/page-1",
        current_target_id="page-1",
        current_target_title="Example",
        current_target_url="about:blank",
        last_known_url="about:blank",
        pending_navigation_url="",
    )
