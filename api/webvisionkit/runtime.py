from __future__ import annotations

import base64
import json
import math
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .actions import execute_operations, update_viewport_state
from .apps import BrowserController, FrameContext, LoadedApp, StreamController, load_app
from .cdp import CDPClient, WebSocketConnectionClosedException, WebSocketTimeoutException
from .deps import cv2, np
from .diagnostics import probe_and_connect_page_client
from .errors import ChromeProbeError, FatalStreamError, RecoverableStreamError, TargetClosedError
from .models import InteractionState, SessionState, StreamConfig, StreamRateState, TargetState
from .targets import (
    build_target_state,
    clear_current_target,
    interruptible_sleep,
    note_last_known_url,
    prepare_target_after_close,
    update_target_state_from_event,
)


def _handle_sigterm(signum: int, frame: Any) -> None:
    raise KeyboardInterrupt


def install_signal_handlers() -> None:
    signal.signal(signal.SIGTERM, _handle_sigterm)


def analyze_frame(frame: np.ndarray) -> Dict[str, Any]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    return {
        "width": int(frame.shape[1]),
        "height": int(frame.shape[0]),
        "mean_gray": round(float(gray.mean()), 2),
        "edge_density": round(float((edges > 0).mean()), 4),
    }


def decode_frame(data_b64: str) -> np.ndarray:
    raw = base64.b64decode(data_b64)
    arr = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("cv2.imdecode returned None")
    return frame


def estimate_latency_ms(metadata: Dict[str, Any]) -> Optional[float]:
    ts = metadata.get("timestamp")
    if ts is None:
        return None
    try:
        return round(max((time.time() - float(ts)) * 1000.0, 0.0), 2)
    except (TypeError, ValueError):
        return None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FrameProcessor:
    name = "base"

    def process(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        return frame, {}


class EdgeOverlayProcessor(FrameProcessor):
    name = "edges"

    def process(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        overlay = frame.copy()
        overlay[edges > 0] = (0, 255, 0)
        return overlay, {"edge_pixels": int((edges > 0).sum())}


class MotionDiffProcessor(FrameProcessor):
    name = "motion"

    def __init__(self) -> None:
        self.previous_gray: Optional[np.ndarray] = None

    def process(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.previous_gray is None:
            self.previous_gray = gray
            return frame, {"motion_score": 0.0}

        diff = cv2.absdiff(gray, self.previous_gray)
        _, mask = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        overlay = frame.copy()
        overlay[mask > 0] = (0, 0, 255)
        motion_score = float((mask > 0).mean())
        self.previous_gray = gray
        return overlay, {"motion_score": round(motion_score, 4)}


def build_processors(names: List[str]) -> List[FrameProcessor]:
    processors: List[FrameProcessor] = []
    for name in names:
        if name == "edges":
            processors.append(EdgeOverlayProcessor())
        elif name == "motion":
            processors.append(MotionDiffProcessor())
        else:
            raise FatalStreamError(f"Unknown processor: {name}. Supported values are edges and motion.")
    return processors


class OutputManager:
    def __init__(self, config: StreamConfig) -> None:
        self.config = config
        self.save_dir = Path(config.save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.preview_ready = False
        self.video_path = self._resolve_optional_path(config.video_output)
        self.metadata_path = self._resolve_optional_path(config.metadata_output)
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.metadata_file = None

        if self.metadata_path is not None:
            self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
            self.metadata_file = self.metadata_path.open("a", encoding="utf-8")
            print(f"[info] Writing frame metadata to {self.metadata_path}")

        if self.video_path is not None:
            self.video_path.parent.mkdir(parents=True, exist_ok=True)
            print(f"[info] Writing processed video to {self.video_path}")

    def _resolve_optional_path(self, raw_path: str) -> Optional[Path]:
        if not raw_path:
            return None
        path = Path(raw_path)
        if not path.is_absolute():
            path = self.save_dir / path
        return path

    def _ensure_video_writer(self, frame: np.ndarray) -> None:
        if self.video_path is None or self.video_writer is not None:
            return

        height, width = frame.shape[:2]
        suffix = self.video_path.suffix.lower()
        fourcc = "mp4v" if suffix in {".mp4", ".m4v", ".mov"} else "MJPG"
        writer = cv2.VideoWriter(
            str(self.video_path),
            cv2.VideoWriter_fourcc(*fourcc),
            self.config.video_fps,
            (width, height),
        )
        if not writer.isOpened():
            raise FatalStreamError(f"Failed to open video writer for {self.video_path}")
        self.video_writer = writer

    def maybe_write_video(self, frame: np.ndarray) -> None:
        if self.video_path is None:
            return
        self._ensure_video_writer(frame)
        assert self.video_writer is not None
        self.video_writer.write(frame)

    def maybe_write_metadata(self, record: Dict[str, Any]) -> None:
        if self.metadata_file is None:
            return
        self.metadata_file.write(json.dumps(record, sort_keys=True) + "\n")
        self.metadata_file.flush()

    def maybe_show_preview(self, frame: np.ndarray) -> bool:
        if not self.config.live_preview:
            return False

        try:
            if not self.preview_ready:
                cv2.namedWindow("Chrome Stream", cv2.WINDOW_NORMAL)
                self.preview_ready = True
            cv2.imshow("Chrome Stream", frame)
            key = cv2.waitKey(1) & 0xFF
        except cv2.error as exc:
            raise FatalStreamError(
                "Live preview failed. Disable it with --no-live-preview or unset LIVE_PREVIEW."
            ) from exc

        return key in {27, ord("q")}

    def handle_frame(self, frame: np.ndarray, record: Dict[str, Any]) -> bool:
        self.maybe_write_video(frame)
        self.maybe_write_metadata(record)
        return self.maybe_show_preview(frame)

    def close(self) -> None:
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None

        if self.metadata_file is not None:
            self.metadata_file.close()
            self.metadata_file = None

        if self.preview_ready:
            try:
                cv2.destroyAllWindows()
            except cv2.error:
                pass


def log_frame(config: StreamConfig, state: SessionState, record: Dict[str, Any]) -> None:
    now = time.monotonic()
    has_action_results = bool(record.get("action_results"))
    if (
        not has_action_results
        and state.last_log_monotonic
        and config.log_interval_seconds > 0
        and now - state.last_log_monotonic < config.log_interval_seconds
    ):
        return

    processor_bits: List[str] = []
    for name, values in record.get("processor_metrics", {}).items():
        metrics_str = ", ".join(f"{key}={value}" for key, value in values.items())
        processor_bits.append(f"{name}({metrics_str})")

    extra = ""
    if processor_bits:
        extra = " " + " ".join(processor_bits)

    latency = record.get("latency_ms")
    latency_str = f" latency_ms={latency}" if latency is not None else ""
    action_bits: List[str] = []
    for action_result in record.get("action_results", []):
        if not isinstance(action_result, dict):
            continue
        action_type = action_result.get("type")
        status = action_result.get("status")
        if action_type and status:
            action_bits.append(f"{action_type}:{status}")
    action_str = f" actions={','.join(action_bits)}" if action_bits else ""

    print(
        f"[frame {record['global_frame_index']}] "
        f"session={state.session_index} "
        f"{record['width']}x{record['height']} "
        f"fps={record['fps']} "
        f"target_fps={record['target_fps']} "
        f"mean_gray={record['mean_gray']} "
        f"edge_density={record['edge_density']}"
        f"{latency_str}{extra}"
        f"{action_str}"
    )
    state.last_log_monotonic = now


def apply_processors(frame: np.ndarray, processors: List[FrameProcessor]) -> Tuple[np.ndarray, Dict[str, Dict[str, Any]]]:
    processed = frame
    processor_metrics: Dict[str, Dict[str, Any]] = {}
    for processor in processors:
        processed, metrics = processor.process(processed)
        processor_metrics[processor.name] = metrics
    return processed, processor_metrics


def build_app_context(
    app: LoadedApp,
    outputs: OutputManager,
    state: SessionState,
    target_state: TargetState,
    interaction_state: InteractionState,
    rate_state: StreamRateState,
    browser: BrowserController,
    record: Dict[str, Any],
) -> FrameContext:
    return FrameContext(
        state=app.state,
        browser=browser,
        stream=StreamController(rate_state),
        frame_index=state.total_frames_seen,
        session_index=state.session_index,
        url=target_state.current_target_url,
        frame_width=interaction_state.viewport.frame_width,
        frame_height=interaction_state.viewport.frame_height,
        save_dir=outputs.save_dir,
        captured_at=record["captured_at"],
        recent_action_results=[dict(item) for item in interaction_state.recent_action_results],
    )


def start_screencast(client: CDPClient, config: StreamConfig, target_state: TargetState) -> None:
    client.call("Page.enable")
    client.call("Runtime.enable")
    client.call("Page.bringToFront")

    if target_state.pending_navigation_url:
        navigation_url = target_state.pending_navigation_url
        print(f"[info] Navigating target to: {navigation_url}")
        client.call("Page.navigate", {"url": navigation_url})
        note_last_known_url(target_state, navigation_url)
        target_state.pending_navigation_url = ""

    params: Dict[str, Any] = {
        "format": config.frame_format,
        "quality": config.frame_quality,
        "everyNthFrame": config.every_nth_frame,
    }
    if config.max_width > 0:
        params["maxWidth"] = config.max_width
    if config.max_height > 0:
        params["maxHeight"] = config.max_height

    client.call("Page.startScreencast", params)


def should_deliver_frame(rate_state: StreamRateState, now_monotonic: float) -> bool:
    if rate_state.next_frame_due_monotonic <= 0:
        return True
    return now_monotonic >= rate_state.next_frame_due_monotonic


def schedule_next_frame(rate_state: StreamRateState) -> None:
    interval_seconds = 1.0 / max(rate_state.callback_fps, 1e-6)
    rate_state.next_frame_due_monotonic = time.monotonic() + interval_seconds


def run_session(
    config: StreamConfig,
    processors: List[FrameProcessor],
    app: LoadedApp,
    outputs: OutputManager,
    state: SessionState,
    target_state: TargetState,
    interaction_state: InteractionState,
    rate_state: StreamRateState,
) -> int:
    client: Optional[CDPClient] = None
    last_frame_monotonic = time.monotonic()
    interaction_state.reset_transient_state()

    try:
        client = probe_and_connect_page_client(config, target_state)
        print("[info] WebSocket connected")
        start_screencast(client, config, target_state)
        print("[info] Screencast started. Ctrl+C to stop.")

        while True:
            try:
                message = client.recv_event()
            except WebSocketTimeoutException:
                if time.monotonic() - last_frame_monotonic >= config.idle_timeout_seconds:
                    raise RecoverableStreamError(
                        f"No screencast frames received for {config.idle_timeout_seconds} seconds."
                    )
                continue
            except TimeoutError:
                if time.monotonic() - last_frame_monotonic >= config.idle_timeout_seconds:
                    raise RecoverableStreamError(
                        f"No screencast frames received for {config.idle_timeout_seconds} seconds."
                    )
                continue
            except (OSError, WebSocketConnectionClosedException) as exc:
                raise RecoverableStreamError("The DevTools websocket connection closed unexpectedly.") from exc

            method = message.get("method")
            update_target_state_from_event(target_state, message)
            if method in {"Page.frameNavigated", "Page.navigatedWithinDocument"}:
                interaction_state.viewport.dirty = True

            if method in {"Inspector.detached", "Target.detachedFromTarget"}:
                params = message.get("params", {})
                reason = str(params.get("reason") or params.get("message") or "target detached")
                clear_current_target(target_state, invalidate_initial_hint=True)
                if reason == "target_closed":
                    raise TargetClosedError(reason)
                raise RecoverableStreamError(f"Chrome detached the target: {reason}")

            if method != "Page.screencastFrame":
                if "error" in message:
                    print(f"[warn] CDP error: {message['error']}", file=sys.stderr)
                continue

            params = message.get("params", {})
            session_id = params.get("sessionId")
            data_b64 = params.get("data")
            if not session_id or not data_b64:
                print("[warn] Invalid screencast frame payload", file=sys.stderr)
                continue

            client.send_cmd("Page.screencastFrameAck", {"sessionId": session_id})

            try:
                frame = decode_frame(data_b64)
            except Exception as exc:
                print(f"[warn] Failed to decode frame: {exc}", file=sys.stderr)
                continue

            last_frame_monotonic = time.monotonic()
            base_metrics = analyze_frame(frame)
            update_viewport_state(
                client,
                interaction_state,
                base_metrics["width"],
                base_metrics["height"],
                params.get("metadata") or {},
            )

            if not should_deliver_frame(rate_state, last_frame_monotonic):
                continue

            state.session_frames_seen += 1
            state.total_frames_seen += 1

            processed_frame, processor_metrics = apply_processors(frame, processors)
            elapsed = max(last_frame_monotonic - state.session_start_monotonic, 1e-6)
            fps = round(state.session_frames_seen / elapsed, 2)
            latency_ms = estimate_latency_ms(params.get("metadata") or {})

            record: Dict[str, Any] = {
                "captured_at": now_iso(),
                "app_name": app.name,
                "session_index": state.session_index,
                "session_frame_index": state.session_frames_seen,
                "global_frame_index": state.total_frames_seen,
                "fps": fps,
                "target_fps": round(rate_state.callback_fps, 2),
                "latency_ms": latency_ms,
                "processor_metrics": processor_metrics,
                **base_metrics,
            }

            browser = BrowserController()
            app_result = app.call(
                processed_frame,
                build_app_context(app, outputs, state, target_state, interaction_state, rate_state, browser, record),
            )
            raw_operations = browser.drain()
            advanced_actions = app_result.pop("actions", None)
            if advanced_actions:
                if not isinstance(advanced_actions, list):
                    raw_operations.append({"type": "__invalid__"})
                else:
                    raw_operations.extend(advanced_actions)
            if app_result:
                record.update(app_result)

            requested_actions, action_results = execute_operations(
                client,
                config,
                app.name,
                interaction_state,
                target_state,
                raw_operations,
            )
            if requested_actions:
                record["requested_actions"] = requested_actions
            if action_results:
                record["action_results"] = action_results

            log_frame(config, state, record)

            if outputs.handle_frame(processed_frame, record):
                print("[info] Preview requested shutdown.")
                return 0

            if config.max_frames > 0 and state.total_frames_seen >= config.max_frames:
                print(f"[info] Reached MAX_FRAMES={config.max_frames}.")
                return 0

            schedule_next_frame(rate_state)

    finally:
        if client is not None:
            if interaction_state.pointer.buttons:
                try:
                    client.call("Input.cancelDragging")
                except Exception:
                    pass
            try:
                client.send_cmd("Page.stopScreencast")
            except Exception:
                pass
            client.close()


def run_loaded_app(config: StreamConfig, app: LoadedApp) -> int:
    processors = build_processors(config.processors)
    outputs = OutputManager(config)
    target_state = build_target_state(config)
    interaction_state = InteractionState()
    rate_state = StreamRateState(callback_fps=app.definition.fps)
    total_frames_seen = 0
    attempts = 0

    print(f"[info] DevTools endpoint base: {config.http_base}")
    if processors:
        print(f"[info] Enabled processors: {', '.join(processor.name for processor in processors)}")
    print(f"[info] Running app: {app.name}")
    print(f"[info] Effective start target: {config.start_target_url}")
    print(f"[info] Initial callback FPS: {rate_state.callback_fps:.2f}")
    print(f"[info] Action mode: {config.action_mode}")

    try:
        while True:
            attempts += 1
            state = SessionState(session_index=attempts, total_frames_seen=total_frames_seen)

            try:
                run_session(config, processors, app, outputs, state, target_state, interaction_state, rate_state)
                return 0
            except TargetClosedError as exc:
                total_frames_seen = state.total_frames_seen
                interaction_state.reset_transient_state()

                if config.target_close_action == "exit":
                    print(f"[info] Target closed ({exc.reason}). Stopping cleanly.")
                    return 0

                limit = config.reconnect_attempts
                if limit > 0 and attempts >= limit:
                    print(f"[error] {exc}", file=sys.stderr)
                    print(f"[error] Reconnect limit reached ({limit} attempts).", file=sys.stderr)
                    return 1

                print(f"[info] Target closed ({exc.reason}). Reopening the last known URL.")
                try:
                    prepare_target_after_close(config, target_state)
                except RecoverableStreamError as reopen_exc:
                    print(f"[error] {reopen_exc}", file=sys.stderr)
                    return 1

                delay = min(config.reconnect_delay_seconds * attempts, 15.0)
                suffix = "unbounded" if limit == 0 else f"{attempts}/{limit}"
                print(f"[info] Reconnecting in {delay:.1f}s after reopening the target (attempt {suffix}).")
                interruptible_sleep(delay)
            except ChromeProbeError as exc:
                total_frames_seen = state.total_frames_seen
                interaction_state.reset_transient_state()

                limit = config.reconnect_attempts
                if limit > 0 and attempts >= limit:
                    print(f"[error] Chrome probe failed at stage {exc.stage!r}: {exc}", file=sys.stderr)
                    print(f"[error] Reconnect limit reached ({limit} attempts).", file=sys.stderr)
                    return 1

                delay = min(config.reconnect_delay_seconds * attempts, 15.0)
                suffix = "unbounded" if limit == 0 else f"{attempts}/{limit}"
                print(f"[warn] Chrome probe failed at stage {exc.stage!r}: {exc}", file=sys.stderr)
                print(f"[info] Reconnecting in {delay:.1f}s (attempt {suffix}).")
                if exc.stage in {"browser-ws", "page-target", "page-ws"}:
                    clear_current_target(target_state, invalidate_initial_hint=True)
                    target_state.browser_ws_url = ""
                interruptible_sleep(delay)
            except RecoverableStreamError as exc:
                total_frames_seen = state.total_frames_seen
                interaction_state.reset_transient_state()

                limit = config.reconnect_attempts
                if limit > 0 and attempts >= limit:
                    print(f"[error] {exc}", file=sys.stderr)
                    print(f"[error] Reconnect limit reached ({limit} attempts).", file=sys.stderr)
                    return 1

                delay = min(config.reconnect_delay_seconds * attempts, 15.0)
                suffix = "unbounded" if limit == 0 else f"{attempts}/{limit}"
                print(f"[warn] {exc}", file=sys.stderr)
                print(f"[info] Reconnecting in {delay:.1f}s (attempt {suffix}).")
                interruptible_sleep(delay)
    except KeyboardInterrupt:
        print("\n[info] Stopping.")
        return 130
    finally:
        outputs.close()


def run_stream(config: StreamConfig) -> int:
    return run_loaded_app(config, load_app(config))
