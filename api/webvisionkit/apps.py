from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .actions import BrowserActions
from .config import validate_positive_fps
from .errors import FatalStreamError
from .models import StreamConfig, StreamRateState


@dataclass
class BrowserApp:
    start_target: str
    fps: float
    on_frame: Callable[[Any, "FrameContext"], Optional[Dict[str, Any]]]

    def __post_init__(self) -> None:
        start_target = str(self.start_target or "").strip()
        if not start_target:
            raise ValueError("BrowserApp start_target must not be empty.")
        self.start_target = start_target
        self.fps = validate_positive_fps(self.fps)
        if not callable(self.on_frame):
            raise ValueError("BrowserApp on_frame must be callable.")


@dataclass
class LoadedApp:
    name: str
    definition: BrowserApp
    state: Dict[str, Any] = field(default_factory=dict)

    def call(self, frame: Any, context: "FrameContext") -> Dict[str, Any]:
        try:
            result = self.definition.on_frame(frame, context)
        except FatalStreamError:
            raise
        except Exception as exc:
            raise FatalStreamError(f"App {self.name!r} failed inside on_frame: {exc}") from exc

        if result is None:
            return {}
        if not isinstance(result, dict):
            raise FatalStreamError(
                f"App {self.name!r} must return a dict or None from on_frame, got {type(result).__name__}."
            )
        return result


class BrowserController:
    def __init__(self) -> None:
        self._operations: List[Dict[str, Any]] = []

    def open(self, url: str, *, name: Any = None, reason: Any = None) -> None:
        text = str(url or "").strip()
        if not text:
            raise ValueError("browser.open(url) requires a non-empty URL.")
        if text.startswith("game://"):
            raise ValueError("game:// targets must be resolved by the launcher before the container starts.")
        operation: Dict[str, Any] = {
            "type": "open_url",
            "url": text,
        }
        if name is not None:
            operation["name"] = str(name)
        if reason is not None:
            operation["reason"] = str(reason)
        self._operations.append(operation)

    def move(self, x: Any, y: Any, **kwargs: Any) -> None:
        self._operations.append(BrowserActions.mouse_move(x, y, **kwargs))

    def mouse_down(self, x: Any = None, y: Any = None, **kwargs: Any) -> None:
        self._operations.append(BrowserActions.mouse_down(x, y, **kwargs))

    def mouse_up(self, x: Any = None, y: Any = None, **kwargs: Any) -> None:
        self._operations.append(BrowserActions.mouse_up(x, y, **kwargs))

    def click(self, x: Any, y: Any, **kwargs: Any) -> None:
        self._operations.append(BrowserActions.click(x, y, **kwargs))

    def double_click(self, x: Any, y: Any, **kwargs: Any) -> None:
        self._operations.append(BrowserActions.double_click(x, y, **kwargs))

    def drag(self, x: Any, y: Any, end_x: Any, end_y: Any, **kwargs: Any) -> None:
        self._operations.append(BrowserActions.drag(x, y, end_x, end_y, **kwargs))

    def scroll(self, x: Any, y: Any, **kwargs: Any) -> None:
        self._operations.append(BrowserActions.scroll(x, y, **kwargs))

    def key_down(self, key: Any, **kwargs: Any) -> None:
        self._operations.append(BrowserActions.key_down(key, **kwargs))

    def key_up(self, key: Any, **kwargs: Any) -> None:
        self._operations.append(BrowserActions.key_up(key, **kwargs))

    def key_press(self, key: Any, **kwargs: Any) -> None:
        self._operations.append(BrowserActions.key_press(key, **kwargs))

    def type_text(self, text: Any, **kwargs: Any) -> None:
        self._operations.append(BrowserActions.type_text(text, **kwargs))

    def pause(self, duration_ms: Any, **kwargs: Any) -> None:
        self._operations.append(BrowserActions.pause(duration_ms, **kwargs))

    def queue_action(self, action: Dict[str, Any]) -> None:
        self._operations.append(dict(action))

    def drain(self) -> List[Dict[str, Any]]:
        operations = list(self._operations)
        self._operations.clear()
        return operations


class StreamController:
    def __init__(self, rate_state: StreamRateState) -> None:
        self._rate_state = rate_state

    def set_fps(self, fps: float) -> float:
        value = validate_positive_fps(fps)
        previous = self._rate_state.callback_fps
        self._rate_state.callback_fps = value
        if not math.isclose(previous, value, rel_tol=0.0, abs_tol=1e-9):
            print(f"[info] Stream callback FPS set to {value:.2f}")
        return value

    def get_fps(self) -> float:
        return float(self._rate_state.callback_fps)


@dataclass
class FrameContext:
    state: Dict[str, Any]
    browser: BrowserController
    stream: StreamController
    frame_index: int
    session_index: int
    url: str
    frame_width: int
    frame_height: int
    save_dir: Path
    captured_at: str
    recent_action_results: List[Dict[str, Any]]


def discover_apps(apps_dir: Path) -> List[str]:
    if not apps_dir.exists():
        return []

    names: List[str] = []
    for child in sorted(apps_dir.iterdir()):
        if child.is_dir() and (child / "app.py").is_file():
            names.append(child.name)
    return names


def ensure_apps_import_path(apps_dir: Path, app_dir: Path) -> None:
    for path in (apps_dir.resolve(), app_dir.resolve()):
        resolved = str(path)
        if resolved not in sys.path:
            sys.path.insert(0, resolved)


def choose_app_name(config: StreamConfig, available_names: List[str]) -> str:
    configured_name = config.app_name.strip()
    if configured_name:
        if configured_name not in available_names:
            joined = ", ".join(available_names)
            raise FatalStreamError(f"Unknown app {configured_name!r}. Available apps: {joined}")
        return configured_name

    if not available_names:
        raise FatalStreamError(f"No apps were found in {config.apps_dir}.")
    return available_names[0]


def load_app(config: StreamConfig) -> LoadedApp:
    apps_dir = Path(config.apps_dir)
    available_names = discover_apps(apps_dir)
    if not available_names:
        raise FatalStreamError(f"No apps found in {apps_dir}. Add subdirectories containing app.py.")

    app_name = choose_app_name(config, available_names)
    app_dir = apps_dir / app_name
    module_path = app_dir / "app.py"
    ensure_apps_import_path(apps_dir, app_dir)

    module_name = f"webvisionkit_app_{app_name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise FatalStreamError(f"Failed to load app module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app = getattr(module, "app", None)
    if not isinstance(app, BrowserApp):
        raise FatalStreamError(f"App {app_name!r} must export app = BrowserApp(...).")

    return LoadedApp(name=app_name, definition=app)


def inspect_app_definition(config: StreamConfig) -> Dict[str, Any]:
    loaded = load_app(config)
    return {
        "name": loaded.name,
        "start_target": loaded.definition.start_target,
        "fps": loaded.definition.fps,
    }
