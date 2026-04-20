from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Tuple

from .cdp import CDPClient
from .deps import np
from .errors import RecoverableStreamError
from .models import InteractionState, StreamConfig, TargetState
from .targets import note_last_known_url


def to_jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return str(value)


def coerce_float(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be numeric, got boolean.")
    if not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite.")
    return number


def coerce_int(value: Any, label: str) -> int:
    return int(round(coerce_float(value, label)))


def action_status_result(
    action: Dict[str, Any],
    index: int,
    status: str,
    message: str = "",
    **extra: Any,
) -> Dict[str, Any]:
    result = {
        "index": index,
        "type": str(action.get("type") or ""),
        "name": str(action.get("name") or ""),
        "status": status,
    }
    if message:
        result["message"] = message
    for key, value in extra.items():
        result[key] = to_jsonable(value)
    return result


def normalize_screencast_metadata(metadata: Any) -> Dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    normalized = dict(metadata)
    normalized["pageScaleFactor"] = coerce_float(normalized.get("pageScaleFactor", 1.0), "pageScaleFactor")
    normalized["offsetTop"] = coerce_float(normalized.get("offsetTop", 0.0), "offsetTop")
    normalized["deviceWidth"] = coerce_float(normalized.get("deviceWidth", 0.0), "deviceWidth")
    normalized["deviceHeight"] = coerce_float(normalized.get("deviceHeight", 0.0), "deviceHeight")
    normalized["scrollOffsetX"] = coerce_float(normalized.get("scrollOffsetX", 0.0), "scrollOffsetX")
    normalized["scrollOffsetY"] = coerce_float(normalized.get("scrollOffsetY", 0.0), "scrollOffsetY")
    return normalized


def refresh_viewport_state(client: CDPClient, interaction_state: InteractionState) -> None:
    layout_metrics = client.call("Page.getLayoutMetrics")
    visual_viewport = ((layout_metrics.get("cssVisualViewport") or {}) if isinstance(layout_metrics, dict) else {}) or {}
    scale = float(visual_viewport.get("scale") or 1.0)
    zoom = float(visual_viewport.get("zoom") or 1.0)
    interaction_state.viewport.css_page_x = float(visual_viewport.get("pageX") or 0.0)
    interaction_state.viewport.css_page_y = float(visual_viewport.get("pageY") or 0.0)
    interaction_state.viewport.css_viewport_width = float(visual_viewport.get("clientWidth") or 0.0)
    interaction_state.viewport.css_viewport_height = float(visual_viewport.get("clientHeight") or 0.0)
    interaction_state.viewport.css_scale = scale if math.isfinite(scale) and scale > 0 else 1.0
    interaction_state.viewport.css_zoom = zoom if math.isfinite(zoom) and zoom > 0 else 1.0
    interaction_state.viewport.dirty = False


def update_viewport_state(
    client: CDPClient,
    interaction_state: InteractionState,
    frame_width: int,
    frame_height: int,
    metadata: Dict[str, Any],
) -> None:
    interaction_state.viewport.frame_width = frame_width
    interaction_state.viewport.frame_height = frame_height
    interaction_state.viewport.screencast_metadata = normalize_screencast_metadata(metadata)
    if interaction_state.viewport.dirty or not interaction_state.viewport.css_viewport_width:
        refresh_viewport_state(client, interaction_state)


def normalize_button(raw_button: Any, default: str = "left") -> str:
    value = str(raw_button or default).strip().lower()
    if value not in {"left", "middle", "right", "back", "forward"}:
        raise ValueError(f"Unsupported mouse button {value!r}.")
    return value


def button_bit(button: str) -> int:
    mapping = {"left": 1, "right": 2, "middle": 4, "back": 8, "forward": 16}
    return mapping[button]


def parse_modifiers(raw_modifiers: Any) -> int:
    if raw_modifiers in (None, "", []):
        return 0
    if isinstance(raw_modifiers, int):
        if raw_modifiers < 0:
            raise ValueError("modifiers must not be negative.")
        return raw_modifiers
    if isinstance(raw_modifiers, str):
        values = [raw_modifiers]
    elif isinstance(raw_modifiers, list):
        values = raw_modifiers
    else:
        raise ValueError("modifiers must be an int, string, or list of strings.")

    mapping = {"alt": 1, "ctrl": 2, "meta": 4, "shift": 8}
    bitmask = 0
    for value in values:
        key = str(value).strip().lower()
        if key not in mapping:
            raise ValueError(f"Unsupported modifier {value!r}.")
        bitmask |= mapping[key]
    return bitmask


def action_fingerprint(source_name: str, action: Dict[str, Any], index: int) -> str:
    explicit = str(action.get("name") or "").strip()
    if explicit:
        return explicit
    return f"{source_name}:{action.get('type', 'unknown')}:{index}:{json.dumps(to_jsonable(action), sort_keys=True)}"


def reject_legacy_coordinate_space(action: Dict[str, Any]) -> None:
    if "coordinate_space" in action:
        raise ValueError("coordinate_space is no longer supported. Action coordinates must already be frame pixels.")


def resolve_frame_point(
    action: Dict[str, Any],
    interaction_state: InteractionState,
    x_key: str = "x",
    y_key: str = "y",
) -> Tuple[float, float]:
    reject_legacy_coordinate_space(action)
    x = coerce_float(action.get(x_key), x_key)
    y = coerce_float(action.get(y_key), y_key)

    frame_width = interaction_state.viewport.frame_width
    frame_height = interaction_state.viewport.frame_height
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("Frame dimensions are unavailable for coordinate mapping.")
    if x < 0 or x > frame_width:
        raise ValueError(f"{x_key}={x} is outside the current frame width {frame_width}.")
    if y < 0 or y > frame_height:
        raise ValueError(f"{y_key}={y} is outside the current frame height {frame_height}.")
    return (x, y)


def frame_to_css_point(interaction_state: InteractionState, frame_x: float, frame_y: float) -> Tuple[float, float]:
    viewport = interaction_state.viewport
    if viewport.frame_width <= 0 or viewport.frame_height <= 0:
        raise ValueError("Frame dimensions are unavailable for coordinate mapping.")
    if viewport.css_viewport_width <= 0 or viewport.css_viewport_height <= 0:
        raise ValueError("Browser viewport metrics are unavailable for coordinate mapping.")

    css_x = viewport.css_page_x + (frame_x / viewport.frame_width) * viewport.css_viewport_width
    css_y = viewport.css_page_y + (frame_y / viewport.frame_height) * viewport.css_viewport_height
    return (css_x, css_y)


def dispatch_mouse_event(
    client: CDPClient,
    interaction_state: InteractionState,
    event_type: str,
    *,
    frame_x: float,
    frame_y: float,
    button: str = "none",
    buttons: int = 0,
    click_count: int = 0,
    modifiers: int = 0,
    delta_x: float = 0.0,
    delta_y: float = 0.0,
) -> None:
    css_x, css_y = frame_to_css_point(interaction_state, frame_x, frame_y)
    client.call(
        "Input.dispatchMouseEvent",
        {
            "type": event_type,
            "x": css_x,
            "y": css_y,
            "button": button,
            "buttons": buttons,
            "clickCount": click_count,
            "modifiers": modifiers,
            "deltaX": delta_x,
            "deltaY": delta_y,
        },
    )
    interaction_state.pointer.known = True
    interaction_state.pointer.x = frame_x
    interaction_state.pointer.y = frame_y
    interaction_state.pointer.buttons = buttons
    interaction_state.pointer.button = button if buttons else "none"


def key_definition_from_action(action: Dict[str, Any], modifiers: int) -> Dict[str, Any]:
    key = str(action.get("key") or "").strip()
    text = str(action.get("text") or "").strip()
    code = str(action.get("code") or "").strip()
    if not key:
        raise ValueError("Keyboard actions require key.")

    key_aliases = {
        "ArrowUp": ("ArrowUp", "ArrowUp"),
        "ArrowDown": ("ArrowDown", "ArrowDown"),
        "ArrowLeft": ("ArrowLeft", "ArrowLeft"),
        "ArrowRight": ("ArrowRight", "ArrowRight"),
        "Enter": ("Enter", "Enter"),
        "Space": (" ", "Space"),
        "Backspace": ("Backspace", "Backspace"),
        "Tab": ("Tab", "Tab"),
        "Escape": ("Escape", "Escape"),
    }

    mapped_key, mapped_code = key_aliases.get(key, (key, code or key))
    output = {
        "key": mapped_key,
        "code": mapped_code,
        "windowsVirtualKeyCode": int(action.get("windowsVirtualKeyCode") or 0),
        "nativeVirtualKeyCode": int(action.get("nativeVirtualKeyCode") or 0),
        "modifiers": modifiers,
    }
    if text:
        output["text"] = text
        output["unmodifiedText"] = text
    elif len(mapped_key) == 1:
        output["text"] = mapped_key
        output["unmodifiedText"] = mapped_key
    return output


def dispatch_key_event(client: CDPClient, event_type: str, key_definition: Dict[str, Any], modifiers: int) -> None:
    payload = dict(key_definition)
    payload["type"] = event_type
    payload["modifiers"] = modifiers
    client.call("Input.dispatchKeyEvent", payload)


def execute_mouse_sequence_click(
    client: CDPClient,
    interaction_state: InteractionState,
    x: float,
    y: float,
    button: str,
    modifiers: int,
    *,
    click_count: int,
) -> None:
    buttons = button_bit(button)
    dispatch_mouse_event(
        client,
        interaction_state,
        "mouseMoved",
        frame_x=x,
        frame_y=y,
        buttons=interaction_state.pointer.buttons,
        modifiers=modifiers,
    )
    dispatch_mouse_event(
        client,
        interaction_state,
        "mousePressed",
        frame_x=x,
        frame_y=y,
        button=button,
        buttons=buttons,
        click_count=click_count,
        modifiers=modifiers,
    )
    dispatch_mouse_event(
        client,
        interaction_state,
        "mouseReleased",
        frame_x=x,
        frame_y=y,
        button=button,
        buttons=0,
        click_count=click_count,
        modifiers=modifiers,
    )


def execute_drag_action(
    client: CDPClient,
    config: StreamConfig,
    interaction_state: InteractionState,
    action: Dict[str, Any],
    modifiers: int,
) -> Dict[str, Any]:
    start_x, start_y = resolve_frame_point(action, interaction_state)
    end_x, end_y = resolve_frame_point(action, interaction_state, x_key="end_x", y_key="end_y")
    button = normalize_button(action.get("button"), default="left")
    buttons = button_bit(button)

    dispatch_mouse_event(
        client,
        interaction_state,
        "mouseMoved",
        frame_x=start_x,
        frame_y=start_y,
        buttons=interaction_state.pointer.buttons,
        modifiers=modifiers,
    )
    dispatch_mouse_event(
        client,
        interaction_state,
        "mousePressed",
        frame_x=start_x,
        frame_y=start_y,
        button=button,
        buttons=buttons,
        click_count=1,
        modifiers=modifiers,
    )

    steps = max(1, config.action_drag_step_count)
    for step_index in range(1, steps + 1):
        fraction = step_index / steps
        x = start_x + (end_x - start_x) * fraction
        y = start_y + (end_y - start_y) * fraction
        dispatch_mouse_event(
            client,
            interaction_state,
            "mouseMoved",
            frame_x=x,
            frame_y=y,
            button=button,
            buttons=buttons,
            modifiers=modifiers,
        )
        if config.action_drag_step_delay_ms > 0 and step_index < steps:
            from .targets import interruptible_sleep

            interruptible_sleep(config.action_drag_step_delay_ms / 1000.0)

    dispatch_mouse_event(
        client,
        interaction_state,
        "mouseReleased",
        frame_x=end_x,
        frame_y=end_y,
        button=button,
        buttons=0,
        click_count=1,
        modifiers=modifiers,
    )
    return {
        "from": {"x": start_x, "y": start_y},
        "to": {"x": end_x, "y": end_y},
    }


def _coerce_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} must not be empty.")
    return text


def execute_action_request(
    client: CDPClient,
    config: StreamConfig,
    source_name: str,
    interaction_state: InteractionState,
    target_state: TargetState,
    action: Any,
    index: int,
    executed_count: int,
) -> Dict[str, Any]:
    if not isinstance(action, dict):
        return action_status_result({}, index, "invalid", "Action must be a dict.")

    action_type = str(action.get("type") or "").strip()
    if not action_type:
        return action_status_result(action, index, "invalid", "Action requires type.")

    cooldown_ms = config.action_default_cooldown_ms
    if "cooldown_ms" in action:
        try:
            cooldown_ms = max(0, coerce_int(action.get("cooldown_ms"), "cooldown_ms"))
        except ValueError as exc:
            return action_status_result(action, index, "invalid", str(exc))

    action_key = action_fingerprint(source_name, action, index)
    now = __import__("time").monotonic()
    last_executed = interaction_state.action_timestamps.get(action_key)
    if last_executed is not None and cooldown_ms > 0 and (now - last_executed) * 1000.0 < cooldown_ms:
        return action_status_result(action, index, "skipped_cooldown", cooldown_ms=cooldown_ms)

    if config.action_mode == "off":
        return action_status_result(action, index, "skipped_mode", mode=config.action_mode)

    if config.action_max_per_frame > 0 and executed_count >= config.action_max_per_frame:
        return action_status_result(action, index, "skipped_frame_limit", max_per_frame=config.action_max_per_frame)

    try:
        modifiers = parse_modifiers(action.get("modifiers"))
    except ValueError as exc:
        return action_status_result(action, index, "invalid", str(exc))

    preview = config.action_mode == "dry-run"
    try:
        if action_type == "open_url":
            url = _coerce_text(action.get("url"), "url")
            if preview:
                result = action_status_result(action, index, "dry_run", url=url)
            else:
                client.call("Page.navigate", {"url": url})
                target_state.current_target_url = url
                note_last_known_url(target_state, url)
                interaction_state.viewport.dirty = True
                result = action_status_result(action, index, "executed", url=url)
        elif action_type == "mouse_move":
            x, y = resolve_frame_point(action, interaction_state)
            if not preview:
                dispatch_mouse_event(
                    client,
                    interaction_state,
                    "mouseMoved",
                    frame_x=x,
                    frame_y=y,
                    buttons=interaction_state.pointer.buttons,
                    modifiers=modifiers,
                )
            result = action_status_result(action, index, "dry_run" if preview else "executed", x=x, y=y)
        elif action_type == "mouse_down":
            button = normalize_button(action.get("button"), default="left")
            if action.get("x") is not None and action.get("y") is not None:
                x, y = resolve_frame_point(action, interaction_state)
            elif interaction_state.pointer.known:
                x = interaction_state.pointer.x
                y = interaction_state.pointer.y
            else:
                raise ValueError("mouse_down requires x/y or an existing pointer position.")
            buttons = interaction_state.pointer.buttons | button_bit(button)
            if not preview:
                dispatch_mouse_event(
                    client,
                    interaction_state,
                    "mousePressed",
                    frame_x=x,
                    frame_y=y,
                    button=button,
                    buttons=buttons,
                    click_count=1,
                    modifiers=modifiers,
                )
            result = action_status_result(action, index, "dry_run" if preview else "executed", x=x, y=y, button=button)
        elif action_type == "mouse_up":
            if action.get("x") is not None and action.get("y") is not None:
                x, y = resolve_frame_point(action, interaction_state)
            elif interaction_state.pointer.known:
                x = interaction_state.pointer.x
                y = interaction_state.pointer.y
            else:
                raise ValueError("mouse_up requires x/y or an existing pointer position.")
            active_button = interaction_state.pointer.button if interaction_state.pointer.button != "none" else "left"
            button = normalize_button(action.get("button"), default=active_button)
            if not preview:
                dispatch_mouse_event(
                    client,
                    interaction_state,
                    "mouseReleased",
                    frame_x=x,
                    frame_y=y,
                    button=button,
                    buttons=max(0, interaction_state.pointer.buttons & ~button_bit(button)),
                    click_count=1,
                    modifiers=modifiers,
                )
            result = action_status_result(action, index, "dry_run" if preview else "executed", x=x, y=y, button=button)
        elif action_type == "click":
            x, y = resolve_frame_point(action, interaction_state)
            button = normalize_button(action.get("button"), default="left")
            if not preview:
                execute_mouse_sequence_click(
                    client,
                    interaction_state,
                    x,
                    y,
                    button,
                    modifiers,
                    click_count=1,
                )
            result = action_status_result(action, index, "dry_run" if preview else "executed", x=x, y=y, button=button)
        elif action_type == "double_click":
            x, y = resolve_frame_point(action, interaction_state)
            button = normalize_button(action.get("button"), default="left")
            if not preview:
                execute_mouse_sequence_click(
                    client,
                    interaction_state,
                    x,
                    y,
                    button,
                    modifiers,
                    click_count=1,
                )
                execute_mouse_sequence_click(
                    client,
                    interaction_state,
                    x,
                    y,
                    button,
                    modifiers,
                    click_count=2,
                )
            result = action_status_result(action, index, "dry_run" if preview else "executed", x=x, y=y, button=button)
        elif action_type == "drag":
            coordinates = execute_drag_action(client, config, interaction_state, action, modifiers) if not preview else {
                "from": {
                    "x": resolve_frame_point(action, interaction_state)[0],
                    "y": resolve_frame_point(action, interaction_state)[1],
                },
                "to": {
                    "x": resolve_frame_point(action, interaction_state, x_key="end_x", y_key="end_y")[0],
                    "y": resolve_frame_point(action, interaction_state, x_key="end_x", y_key="end_y")[1],
                },
            }
            result = action_status_result(action, index, "dry_run" if preview else "executed", **coordinates)
        elif action_type == "scroll":
            x, y = resolve_frame_point(action, interaction_state)
            delta_x = coerce_float(action.get("delta_x", 0.0), "delta_x")
            delta_y = coerce_float(action.get("delta_y", 0.0), "delta_y")
            if not preview:
                dispatch_mouse_event(
                    client,
                    interaction_state,
                    "mouseWheel",
                    frame_x=x,
                    frame_y=y,
                    modifiers=modifiers,
                    delta_x=delta_x,
                    delta_y=delta_y,
                )
            result = action_status_result(
                action,
                index,
                "dry_run" if preview else "executed",
                x=x,
                y=y,
                delta_x=delta_x,
                delta_y=delta_y,
            )
        elif action_type in {"key_down", "key_up", "key_press"}:
            key_definition = key_definition_from_action(action, modifiers)
            if not preview:
                if action_type == "key_down":
                    dispatch_key_event(client, "keyDown", key_definition, modifiers)
                elif action_type == "key_up":
                    dispatch_key_event(client, "keyUp", key_definition, modifiers)
                else:
                    dispatch_key_event(client, "keyDown", key_definition, modifiers)
                    dispatch_key_event(client, "keyUp", key_definition, modifiers)
            result = action_status_result(
                action,
                index,
                "dry_run" if preview else "executed",
                key=key_definition.get("key"),
                code=key_definition.get("code"),
            )
        elif action_type == "type_text":
            text = str(action.get("text") or "")
            if not text:
                raise ValueError("type_text requires non-empty text.")
            if not preview:
                client.call("Input.insertText", {"text": text})
            result = action_status_result(action, index, "dry_run" if preview else "executed", text=text)
        elif action_type == "pause":
            duration_ms = max(0, coerce_int(action.get("duration_ms"), "duration_ms"))
            if not preview and duration_ms > 0:
                from .targets import interruptible_sleep

                interruptible_sleep(duration_ms / 1000.0)
            result = action_status_result(action, index, "dry_run" if preview else "executed", duration_ms=duration_ms)
        else:
            return action_status_result(action, index, "invalid", f"Unsupported action type: {action_type}")
    except ValueError as exc:
        return action_status_result(action, index, "invalid", str(exc))
    except RecoverableStreamError as exc:
        if "CDP command Input." in str(exc) or action_type == "open_url":
            return action_status_result(action, index, "error", str(exc))
        raise

    interaction_state.action_timestamps[action_key] = now
    return result


def execute_operations(
    client: CDPClient,
    config: StreamConfig,
    source_name: str,
    interaction_state: InteractionState,
    target_state: TargetState,
    raw_operations: Any,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if raw_operations is None:
        return ([], [])

    if not isinstance(raw_operations, list):
        requested = [to_jsonable(raw_operations)]
        results = [action_status_result({}, 0, "invalid", "operations must be a list.")]
        interaction_state.recent_action_results.extend(results)
        return (requested, results)

    requested_operations = [to_jsonable(action) for action in raw_operations]
    results: List[Dict[str, Any]] = []
    executed_count = 0

    for index, action in enumerate(raw_operations):
        result = execute_action_request(
            client,
            config,
            source_name,
            interaction_state,
            target_state,
            action,
            index,
            executed_count,
        )
        results.append(result)
        if result["status"] in {"executed", "dry_run"}:
            executed_count += 1

    interaction_state.recent_action_results.extend(results)
    return (requested_operations, results)


class BrowserActions:
    @staticmethod
    def _apply_common_fields(
        action: Dict[str, Any],
        *,
        name: Any = None,
        reason: Any = None,
        cooldown_ms: Any = None,
        modifiers: Any = None,
    ) -> Dict[str, Any]:
        action = dict(action)
        if name is not None:
            action["name"] = _coerce_text(name, "name")
        if reason is not None:
            action["reason"] = _coerce_text(reason, "reason")
        if cooldown_ms is not None:
            action["cooldown_ms"] = max(0, coerce_int(cooldown_ms, "cooldown_ms"))
        if modifiers is not None:
            action["modifiers"] = modifiers
        return action

    @staticmethod
    def _apply_point(
        action: Dict[str, Any],
        *,
        x: Any = None,
        y: Any = None,
        x_label: str = "x",
        y_label: str = "y",
        required: bool = True,
    ) -> Dict[str, Any]:
        action = dict(action)
        if x is None and y is None and not required:
            return action
        if x is None or y is None:
            raise ValueError(f"{x_label} and {y_label} must be provided together.")
        action[x_label] = coerce_int(x, x_label)
        action[y_label] = coerce_int(y, y_label)
        return action

    @staticmethod
    def mouse_move(x: Any, y: Any, **kwargs: Any) -> Dict[str, Any]:
        action = BrowserActions._apply_point({"type": "mouse_move"}, x=x, y=y)
        return BrowserActions._apply_common_fields(action, **kwargs)

    @staticmethod
    def mouse_down(x: Any = None, y: Any = None, *, button: Any = None, **kwargs: Any) -> Dict[str, Any]:
        action = BrowserActions._apply_point({"type": "mouse_down"}, x=x, y=y, required=False)
        if button is not None:
            action["button"] = str(button)
        return BrowserActions._apply_common_fields(action, **kwargs)

    @staticmethod
    def mouse_up(x: Any = None, y: Any = None, *, button: Any = None, **kwargs: Any) -> Dict[str, Any]:
        action = BrowserActions._apply_point({"type": "mouse_up"}, x=x, y=y, required=False)
        if button is not None:
            action["button"] = str(button)
        return BrowserActions._apply_common_fields(action, **kwargs)

    @staticmethod
    def click(x: Any, y: Any, *, button: Any = None, **kwargs: Any) -> Dict[str, Any]:
        action = BrowserActions._apply_point({"type": "click"}, x=x, y=y)
        if button is not None:
            action["button"] = str(button)
        return BrowserActions._apply_common_fields(action, **kwargs)

    @staticmethod
    def double_click(x: Any, y: Any, *, button: Any = None, **kwargs: Any) -> Dict[str, Any]:
        action = BrowserActions._apply_point({"type": "double_click"}, x=x, y=y)
        if button is not None:
            action["button"] = str(button)
        return BrowserActions._apply_common_fields(action, **kwargs)

    @staticmethod
    def drag(
        x: Any,
        y: Any,
        end_x: Any,
        end_y: Any,
        *,
        button: Any = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        action = BrowserActions._apply_point({"type": "drag"}, x=x, y=y)
        action = BrowserActions._apply_point(action, x=end_x, y=end_y, x_label="end_x", y_label="end_y")
        if button is not None:
            action["button"] = str(button)
        return BrowserActions._apply_common_fields(action, **kwargs)

    @staticmethod
    def scroll(x: Any, y: Any, *, delta_x: Any = 0, delta_y: Any = 0, **kwargs: Any) -> Dict[str, Any]:
        action = BrowserActions._apply_point({"type": "scroll"}, x=x, y=y)
        action["delta_x"] = coerce_float(delta_x, "delta_x")
        action["delta_y"] = coerce_float(delta_y, "delta_y")
        return BrowserActions._apply_common_fields(action, **kwargs)

    @staticmethod
    def key_down(key: Any, *, code: Any = None, text: Any = None, **kwargs: Any) -> Dict[str, Any]:
        action = {"type": "key_down", "key": _coerce_text(key, "key")}
        if code is not None:
            action["code"] = str(code)
        if text is not None:
            action["text"] = str(text)
        return BrowserActions._apply_common_fields(action, **kwargs)

    @staticmethod
    def key_up(key: Any, *, code: Any = None, text: Any = None, **kwargs: Any) -> Dict[str, Any]:
        action = {"type": "key_up", "key": _coerce_text(key, "key")}
        if code is not None:
            action["code"] = str(code)
        if text is not None:
            action["text"] = str(text)
        return BrowserActions._apply_common_fields(action, **kwargs)

    @staticmethod
    def key_press(key: Any, *, code: Any = None, text: Any = None, **kwargs: Any) -> Dict[str, Any]:
        action = {"type": "key_press", "key": _coerce_text(key, "key")}
        if code is not None:
            action["code"] = str(code)
        if text is not None:
            action["text"] = str(text)
        return BrowserActions._apply_common_fields(action, **kwargs)

    @staticmethod
    def type_text(text: Any, **kwargs: Any) -> Dict[str, Any]:
        action = {"type": "type_text", "text": _coerce_text(text, "text")}
        return BrowserActions._apply_common_fields(action, **kwargs)

    @staticmethod
    def pause(duration_ms: Any, **kwargs: Any) -> Dict[str, Any]:
        action = {"type": "pause", "duration_ms": max(0, coerce_int(duration_ms, "duration_ms"))}
        return BrowserActions._apply_common_fields(action, **kwargs)
