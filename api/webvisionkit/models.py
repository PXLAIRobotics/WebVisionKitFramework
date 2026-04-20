from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List


DEFAULT_SAVE_DIR = "/data/output/screenshots"
DEFAULT_APPS_DIR = "/workspace/apps"


@dataclass
class StreamConfig:
    chrome_host: str
    chrome_port: int
    browser_browser_ws_url: str
    browser_ws_url: str
    apps_dir: str
    app_name: str
    app_default_target_url: str
    target_url_override: str
    start_target_url: str
    target_match: str
    target_close_action: str
    startup_target_mode: str
    frame_format: str
    frame_quality: int
    every_nth_frame: int
    max_width: int
    max_height: int
    save_dir: str
    save_interval_seconds: float
    live_preview: bool
    video_output: str
    metadata_output: str
    processors: List[str]
    reconnect_attempts: int
    reconnect_delay_seconds: float
    receive_timeout_seconds: float
    idle_timeout_seconds: float
    log_interval_seconds: float
    video_fps: float
    max_frames: int
    action_mode: str
    action_default_cooldown_ms: int
    action_max_per_frame: int
    action_drag_step_count: int
    action_drag_step_delay_ms: int

    @property
    def http_base(self) -> str:
        return f"http://{self.chrome_host}:{self.chrome_port}"

    @property
    def json_list_url(self) -> str:
        return f"{self.http_base}/json"

    @property
    def json_version_url(self) -> str:
        return f"{self.http_base}/json/version"


@dataclass
class SessionState:
    session_index: int
    total_frames_seen: int
    session_frames_seen: int = 0
    session_start_monotonic: float = field(default_factory=time.monotonic)
    last_log_monotonic: float = 0.0


@dataclass
class TargetState:
    browser_ws_url: str
    initial_page_ws_url: str
    initial_page_ws_url_valid: bool
    startup_target_pending: bool
    current_page_ws_url: str = ""
    current_target_id: str = ""
    current_target_title: str = ""
    current_target_url: str = ""
    last_known_url: str = ""
    pending_navigation_url: str = ""


@dataclass
class PointerState:
    known: bool = False
    x: float = 0.0
    y: float = 0.0
    buttons: int = 0
    button: str = "none"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "known": self.known,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "buttons": self.buttons,
            "button": self.button,
        }


@dataclass
class ViewportState:
    frame_width: int = 0
    frame_height: int = 0
    css_page_x: float = 0.0
    css_page_y: float = 0.0
    css_viewport_width: float = 0.0
    css_viewport_height: float = 0.0
    css_scale: float = 1.0
    css_zoom: float = 1.0
    screencast_metadata: Dict[str, Any] = field(default_factory=dict)
    dirty: bool = True

    def as_dict(self) -> Dict[str, Any]:
        return {
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "css_visual_viewport": {
                "pageX": round(self.css_page_x, 2),
                "pageY": round(self.css_page_y, 2),
                "clientWidth": round(self.css_viewport_width, 2),
                "clientHeight": round(self.css_viewport_height, 2),
                "scale": round(self.css_scale, 4),
                "zoom": round(self.css_zoom, 4),
            },
            "screencast_metadata": dict(self.screencast_metadata),
        }


@dataclass
class InteractionState:
    pointer: PointerState = field(default_factory=PointerState)
    viewport: ViewportState = field(default_factory=ViewportState)
    action_timestamps: Dict[str, float] = field(default_factory=dict)
    recent_action_results: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=50))

    def reset_transient_state(self) -> None:
        self.pointer = PointerState()
        self.viewport = ViewportState(dirty=True)


@dataclass
class StreamRateState:
    callback_fps: float
    next_frame_due_monotonic: float = 0.0
