from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from webvisionkit import BrowserApp


SHOWCASE_URL_TOKEN = "/games/input-lab/index.html"
OBSERVATION_SECONDS = 3.0
ACTION_SUCCESS_STATUSES = {"executed", "dry_run"}
ACTION_FAILURE_STATUSES = {"invalid", "error", "skipped_mode", "skipped_frame_limit"}
WAIT_BLOCK_SECONDS = 10.0
NAVIGATION_RETRY_SECONDS = 1.0
POINTER_HOLD_MS = 180
TEXT_INPUT_VALUE = "Wizard proof."
TEXT_AREA_VALUE = "Step-by-step demo.\nEvidence remains visible."

STEP_ORDER = [
    "pointer",
    "clicks",
    "drag",
    "scroll-panel",
    "page-scroll",
    "text-entry",
    "keyboard",
]

STEP_LABELS = {
    "pointer": "1. Pointer",
    "clicks": "2. Clicks",
    "drag": "3. Drag",
    "scroll-panel": "4. Scroll Panel",
    "page-scroll": "5. Page Scroll",
    "text-entry": "6. Text Entry",
    "keyboard": "7. Keyboard",
}

STEP_BADGES = {
    "pointer": "step_pointer",
    "clicks": "step_clicks",
    "drag": "step_drag",
    "scroll-panel": "step_scroll_panel",
    "page-scroll": "step_page_scroll",
    "text-entry": "step_text_entry",
    "keyboard": "step_keyboard",
}

DETECTION_SCALES = (1.0, 2.0)


MARKER_SPECS: Dict[str, Dict[str, Any]] = {
    "next": {
        "hex_color": "#ff5a5f",
        "hue_tolerance": 7,
        "sat_floor": 110,
        "val_floor": 110,
        "min_white_ring_ratio": 0.45,
        "min_black_ring_ratio": 0.05,
    },
    "proof_complete": {
        "hex_color": "#16c47f",
        "hue_tolerance": 8,
        "sat_floor": 90,
        "val_floor": 90,
        "min_white_ring_ratio": 0.45,
        "min_black_ring_ratio": 0.15,
    },
    "target_primary": {
        "hex_color": "#2f78ff",
        "hue_tolerance": 8,
        "sat_floor": 100,
        "val_floor": 90,
        "min_white_ring_ratio": 0.45,
        "min_black_ring_ratio": 0.15,
    },
    "target_secondary": {
        "hex_color": "#ffbd2e",
        "hue_tolerance": 10,
        "sat_floor": 100,
        "val_floor": 100,
        "min_white_ring_ratio": 0.45,
        "min_black_ring_ratio": 0.15,
    },
    "step_pointer": {
        "hex_color": "#ff4fd8",
        "hue_tolerance": 8,
        "sat_floor": 90,
        "val_floor": 90,
        "min_white_ring_ratio": 0.45,
        "min_black_ring_ratio": 0.15,
    },
    "step_clicks": {
        "hex_color": "#3fd7ff",
        "hue_tolerance": 8,
        "sat_floor": 90,
        "val_floor": 90,
        "min_white_ring_ratio": 0.45,
        "min_black_ring_ratio": 0.15,
    },
    "step_drag": {
        "hex_color": "#9167ff",
        "hue_tolerance": 8,
        "sat_floor": 80,
        "val_floor": 90,
        "min_white_ring_ratio": 0.45,
        "min_black_ring_ratio": 0.15,
    },
    "step_scroll_panel": {
        "hex_color": "#ff9640",
        "hue_tolerance": 8,
        "sat_floor": 90,
        "val_floor": 100,
        "min_white_ring_ratio": 0.45,
        "min_black_ring_ratio": 0.15,
    },
    "step_page_scroll": {
        "hex_color": "#13c2a3",
        "hue_tolerance": 8,
        "sat_floor": 80,
        "val_floor": 80,
        "min_white_ring_ratio": 0.45,
        "min_black_ring_ratio": 0.15,
    },
    "step_text_entry": {
        "hex_color": "#ff6b93",
        "hue_tolerance": 8,
        "sat_floor": 90,
        "val_floor": 90,
        "min_white_ring_ratio": 0.45,
        "min_black_ring_ratio": 0.15,
    },
    "step_keyboard": {
        "hex_color": "#c7a600",
        "hue_tolerance": 8,
        "sat_floor": 90,
        "val_floor": 80,
        "min_white_ring_ratio": 0.45,
        "min_black_ring_ratio": 0.15,
    },
}


def _hex_to_bgr(hex_color: str) -> Tuple[int, int, int]:
    text = hex_color.lstrip("#")
    return int(text[4:6], 16), int(text[2:4], 16), int(text[0:2], 16)


def _hsv_ranges_for_spec(spec: Dict[str, Any]) -> List[Tuple[np.ndarray, np.ndarray]]:
    bgr = _hex_to_bgr(str(spec["hex_color"]))
    hsv = cv2.cvtColor(np.uint8([[[bgr[0], bgr[1], bgr[2]]]]), cv2.COLOR_BGR2HSV)[0, 0]
    hue, sat, val = int(hsv[0]), int(hsv[1]), int(hsv[2])
    hue_low = hue - int(spec["hue_tolerance"])
    hue_high = hue + int(spec["hue_tolerance"])
    sat_low = max(int(spec["sat_floor"]), sat - 90)
    val_low = max(int(spec["val_floor"]), val - 90)

    if hue_low < 0:
        return [
            (np.array([0, sat_low, val_low], dtype=np.uint8), np.array([hue_high, 255, 255], dtype=np.uint8)),
            (np.array([180 + hue_low, sat_low, val_low], dtype=np.uint8), np.array([179, 255, 255], dtype=np.uint8)),
        ]
    if hue_high > 179:
        return [
            (np.array([0, sat_low, val_low], dtype=np.uint8), np.array([hue_high - 180, 255, 255], dtype=np.uint8)),
            (np.array([hue_low, sat_low, val_low], dtype=np.uint8), np.array([179, 255, 255], dtype=np.uint8)),
        ]
    return [
        (
            np.array([hue_low, sat_low, val_low], dtype=np.uint8),
            np.array([hue_high, 255, 255], dtype=np.uint8),
        )
    ]


HSV_RANGES = {name: _hsv_ranges_for_spec(spec) for name, spec in MARKER_SPECS.items()}


def _marker_mask(hsv_image: np.ndarray, marker_name: str) -> np.ndarray:
    mask = np.zeros(hsv_image.shape[:2], dtype=np.uint8)
    for lower, upper in HSV_RANGES[marker_name]:
        mask = cv2.bitwise_or(mask, cv2.inRange(hsv_image, lower, upper))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    return mask


def _ring_ratio(mask: np.ndarray, ring_mask: np.ndarray) -> float:
    total = float(np.count_nonzero(ring_mask))
    if total <= 0.0:
        return 0.0
    return float(np.count_nonzero(mask & ring_mask)) / total


def _is_bullseye(
    frame_bgr: np.ndarray,
    frame_hsv: np.ndarray,
    center_x: int,
    center_y: int,
    radius: float,
    marker_name: str,
) -> bool:
    patch_radius = max(int(round(radius * 2.6)), 14)
    x0 = max(center_x - patch_radius, 0)
    y0 = max(center_y - patch_radius, 0)
    x1 = min(center_x + patch_radius + 1, frame_bgr.shape[1])
    y1 = min(center_y + patch_radius + 1, frame_bgr.shape[0])
    if x1 - x0 < 12 or y1 - y0 < 12:
        return False

    local_hsv = frame_hsv[y0:y1, x0:x1]
    yy, xx = np.ogrid[y0:y1, x0:x1]
    distance = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)

    white_ring = (distance >= radius * 1.1) & (distance <= radius * 1.95)
    black_ring = (distance >= radius * 2.35) & (distance <= radius * 3.2)
    if not np.any(white_ring) or not np.any(black_ring):
        return False

    white_mask = ((local_hsv[:, :, 1] <= 70) & (local_hsv[:, :, 2] >= 180)).astype(np.uint8)
    black_mask = (local_hsv[:, :, 2] <= 120).astype(np.uint8)

    spec = MARKER_SPECS[marker_name]
    white_ratio = _ring_ratio(white_mask, white_ring)
    black_ratio = _ring_ratio(black_mask, black_ring)
    return (
        white_ratio >= float(spec.get("min_white_ring_ratio", 0.45))
        and black_ratio >= float(spec.get("min_black_ring_ratio", 0.25))
    )


def _detect_marker_candidates(frame_bgr: np.ndarray, frame_hsv: np.ndarray, marker_name: str) -> List[Dict[str, Any]]:
    mask = _marker_mask(frame_hsv, marker_name)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    frame_area = frame_bgr.shape[0] * frame_bgr.shape[1]
    min_area = max(8.0, frame_area * 0.000008)
    max_area = frame_area * 0.0035
    min_radius = max(2.0, min(frame_bgr.shape[:2]) * 0.0015)
    max_radius = min(frame_bgr.shape[:2]) * 0.08

    candidates: List[Dict[str, Any]] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area or area > max_area:
            continue
        perimeter = float(cv2.arcLength(contour, True))
        if perimeter <= 0.0:
            continue
        circularity = float(4.0 * np.pi * area / (perimeter * perimeter))
        if circularity < 0.55:
            continue
        (center_x, center_y), radius = cv2.minEnclosingCircle(contour)
        if radius < min_radius or radius > max_radius:
            continue
        cx = int(round(center_x))
        cy = int(round(center_y))
        if not _is_bullseye(frame_bgr, frame_hsv, cx, cy, radius, marker_name):
            continue
        candidates.append(
            {
                "center": (cx, cy),
                "radius": round(float(radius), 2),
                "area": round(area, 2),
                "circularity": round(circularity, 3),
            }
        )

    candidates.sort(key=lambda item: item["area"], reverse=True)
    return candidates


def _rescale_candidate(candidate: Dict[str, Any], scale: float) -> Dict[str, Any]:
    if scale == 1.0:
        return dict(candidate)
    center_x, center_y = candidate["center"]
    return {
        "center": (int(round(center_x / scale)), int(round(center_y / scale))),
        "radius": round(float(candidate["radius"]) / scale, 2),
        "area": round(float(candidate["area"]) / (scale * scale), 2),
        "circularity": float(candidate["circularity"]),
    }


def _merge_candidates(candidate_sets: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    all_candidates = [dict(item) for subset in candidate_sets for item in subset]
    all_candidates.sort(key=lambda item: float(item["area"]), reverse=True)

    for candidate in all_candidates:
        center_x, center_y = candidate["center"]
        duplicate = False
        for existing in merged:
            existing_x, existing_y = existing["center"]
            if abs(center_x - existing_x) <= 6 and abs(center_y - existing_y) <= 6:
                duplicate = True
                break
        if not duplicate:
            merged.append(candidate)

    return merged


def _is_header_badge_center(center: Tuple[int, int], frame_shape: Tuple[int, int, int]) -> bool:
    frame_height, frame_width = frame_shape[:2]
    x, y = center
    return (
        x >= int(frame_width * 0.58)
        and x <= int(frame_width * 0.9)
        and y >= int(frame_height * 0.04)
        and y <= int(frame_height * 0.28)
    )


def detect_markers(frame_bgr: np.ndarray) -> Dict[str, Any]:
    scale_candidates: Dict[str, List[List[Dict[str, Any]]]] = {name: [] for name in MARKER_SPECS}
    for scale in DETECTION_SCALES:
        if scale == 1.0:
            scaled_frame = frame_bgr
        else:
            scaled_frame = cv2.resize(frame_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        hsv = cv2.cvtColor(scaled_frame, cv2.COLOR_BGR2HSV)
        for name in MARKER_SPECS:
            detected = _detect_marker_candidates(scaled_frame, hsv, name)
            scale_candidates[name].append([_rescale_candidate(item, scale) for item in detected])

    candidates = {name: _merge_candidates(scale_candidates[name]) for name in MARKER_SPECS}

    visible_step: Optional[str] = None
    visible_badge: Optional[str] = None
    visible_area = -1.0
    for step_slug, marker_name in STEP_BADGES.items():
        valid_badges = [
            item
            for item in candidates[marker_name]
            if _is_header_badge_center(tuple(item["center"]), frame_bgr.shape)
        ]
        if valid_badges:
            area = float(valid_badges[0]["area"])
            if area > visible_area:
                visible_area = area
                visible_step = step_slug
                visible_badge = marker_name

    return {
        "candidates": candidates,
        "visible_step": visible_step,
        "visible_badge": visible_badge,
        "primary": candidates["target_primary"][0] if candidates["target_primary"] else None,
        "secondary": candidates["target_secondary"][0] if candidates["target_secondary"] else None,
        "next": candidates["next"][0] if candidates["next"] else None,
        "proof_complete": candidates["proof_complete"][0] if candidates["proof_complete"] else None,
    }


def _latest_results_by_name(results: List[dict]) -> Dict[str, dict]:
    latest: Dict[str, dict] = {}
    for item in results:
        name = str(item.get("name") or "").strip()
        if name:
            latest[name] = dict(item)
    return latest


def _marker_center(markers: Dict[str, Any], key: str) -> Optional[Tuple[int, int]]:
    marker = markers.get(key)
    if not marker:
        return None
    return marker["center"]


def _build_marker_debug(markers: Dict[str, Any]) -> Dict[str, Any]:
    candidates = markers["candidates"]
    return {
        "visible_step": markers["visible_step"],
        "visible_badge": markers["visible_badge"],
        "marker_counts": {name: len(items) for name, items in candidates.items()},
        "centers": {
            key: (value["center"] if value else None)
            for key, value in {
                "primary": markers.get("primary"),
                "secondary": markers.get("secondary"),
                "next": markers.get("next"),
                "proof_complete": markers.get("proof_complete"),
            }.items()
        },
    }


def _stage_result(status: str, note: str, *, missing_markers: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "status": status,
        "note": note,
        "missing_markers": list(missing_markers or []),
    }


def _note_wait(showcase_state: Dict[str, Any], reason: str, *, subphase: Optional[str] = None) -> None:
    now = time.monotonic()
    if subphase:
        showcase_state["subphase"] = subphase
    if showcase_state.get("wait_reason") != reason:
        showcase_state["wait_reason"] = reason
        showcase_state["wait_since_monotonic"] = now


def _maybe_block(showcase_state: Dict[str, Any], reason: str) -> None:
    if now := showcase_state.get("wait_since_monotonic"):
        if time.monotonic() - float(now) >= WAIT_BLOCK_SECONDS:
            showcase_state["phase"] = "blocked"
            showcase_state["blocked_reason"] = reason
            showcase_state["subphase"] = "blocked"


def _wait_with_timeout(
    showcase_state: Dict[str, Any],
    reason: str,
    *,
    missing_markers: Optional[List[str]] = None,
    subphase: str,
) -> Dict[str, Any]:
    _note_wait(showcase_state, reason, subphase=subphase)
    _maybe_block(showcase_state, reason)
    if showcase_state.get("phase") == "blocked":
        return _stage_result("blocked", reason, missing_markers=missing_markers)
    return _stage_result("waiting", reason, missing_markers=missing_markers)


def _clear_pending(showcase_state: Dict[str, Any]) -> None:
    showcase_state["pending_action_name"] = ""
    showcase_state["pending_action_label"] = ""
    showcase_state["pending_action_reason"] = ""


def _advance_substep(showcase_state: Dict[str, Any]) -> None:
    showcase_state["substep_index"] = int(showcase_state.get("substep_index", 0)) + 1


def _queue_browser_action(
    context,
    showcase_state: Dict[str, Any],
    step_slug: str,
    label: str,
    reason: str,
    callback: Callable[[str], None],
    *,
    subphase: str,
) -> str:
    action_serial = int(showcase_state.get("action_serial", 0)) + 1
    showcase_state["action_serial"] = action_serial
    action_name = f"interaction_showcase:{step_slug}:{label}:{action_serial}"
    callback(action_name)
    showcase_state["pending_action_name"] = action_name
    showcase_state["pending_action_label"] = label
    showcase_state["pending_action_reason"] = reason
    showcase_state["wait_reason"] = f"Waiting for {label} to finish dispatching."
    showcase_state["wait_since_monotonic"] = time.monotonic()
    showcase_state["subphase"] = subphase
    return action_name


def _resolve_pending_action(context, showcase_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    pending_name = str(showcase_state.get("pending_action_name") or "")
    if not pending_name:
        return None

    results_by_name = _latest_results_by_name(context.recent_action_results)
    result = results_by_name.get(pending_name)
    if not result:
        return {
            "status": "waiting",
            "reason": str(showcase_state.get("pending_action_reason") or "Waiting for the browser action result."),
        }

    status = str(result.get("status") or "")
    if status in ACTION_FAILURE_STATUSES:
        showcase_state["phase"] = "blocked"
        showcase_state["blocked_reason"] = f"Browser action {pending_name!r} failed with status {status}."
        showcase_state["blocked_result"] = dict(result)
        showcase_state["subphase"] = "blocked"
        return {
            "status": "blocked",
            "reason": str(showcase_state["blocked_reason"]),
            "result": dict(result),
        }

    if status in ACTION_SUCCESS_STATUSES:
        _clear_pending(showcase_state)
        showcase_state["wait_reason"] = ""
        showcase_state["wait_since_monotonic"] = 0.0
        return {
            "status": "done",
            "reason": f"{pending_name} finished with status {status}.",
            "result": dict(result),
        }

    return {
        "status": "waiting",
        "reason": f"Waiting for {pending_name} to finish. Latest status: {status or 'pending'}.",
        "result": dict(result),
    }


def _require_stage_visible(
    showcase_state: Dict[str, Any],
    markers: Dict[str, Any],
    step_slug: str,
    required_roles: List[str],
) -> Optional[Dict[str, Any]]:
    if int(showcase_state.get("substep_index", 0)) != 0:
        return None
    if markers.get("visible_step") == step_slug:
        return None
    if all(_marker_center(markers, role) is not None for role in required_roles):
        return None

    badge_name = STEP_BADGES[step_slug]
    return _wait_with_timeout(
        showcase_state,
        f"Waiting for {STEP_LABELS[step_slug]} to become visible or expose its action markers.",
        missing_markers=[badge_name, *required_roles],
        subphase="locate_step",
    )


def _require_markers(
    showcase_state: Dict[str, Any],
    markers: Dict[str, Any],
    step_slug: str,
    roles: List[str],
) -> Tuple[Optional[Dict[str, Tuple[int, int]]], Optional[Dict[str, Any]]]:
    centers = {role: _marker_center(markers, role) for role in roles}
    missing_roles = [role for role, center in centers.items() if center is None]
    if missing_roles:
        return None, _wait_with_timeout(
            showcase_state,
            f"Waiting for the {', '.join(missing_roles)} marker(s) on {STEP_LABELS[step_slug]}.",
            missing_markers=missing_roles,
            subphase="locate_targets",
        )
    return {role: centers[role] for role in roles if centers[role] is not None}, None


def _queue_point_action(
    context,
    showcase_state: Dict[str, Any],
    step_slug: str,
    *,
    kind: str,
    point: Tuple[int, int],
    label: str,
    reason: str,
    advance_substep: bool = True,
) -> Dict[str, Any]:
    x, y = point

    def callback(action_name: str) -> None:
        method = getattr(context.browser, kind)
        method(x, y, name=action_name, cooldown_ms=0, reason=reason)

    _queue_browser_action(context, showcase_state, step_slug, label, reason, callback, subphase=label)
    if advance_substep:
        _advance_substep(showcase_state)
    return _stage_result("queued", reason)


def _queue_drag_action(
    context,
    showcase_state: Dict[str, Any],
    step_slug: str,
    *,
    start: Tuple[int, int],
    end: Tuple[int, int],
    label: str,
    reason: str,
) -> Dict[str, Any]:
    def callback(action_name: str) -> None:
        context.browser.drag(*start, *end, name=action_name, cooldown_ms=0, reason=reason)

    _queue_browser_action(context, showcase_state, step_slug, label, reason, callback, subphase=label)
    _advance_substep(showcase_state)
    return _stage_result("queued", reason)


def _queue_pause_action(
    context,
    showcase_state: Dict[str, Any],
    step_slug: str,
    *,
    duration_ms: int,
    label: str,
    reason: str,
) -> Dict[str, Any]:
    def callback(action_name: str) -> None:
        context.browser.pause(duration_ms, name=action_name, cooldown_ms=0, reason=reason)

    _queue_browser_action(context, showcase_state, step_slug, label, reason, callback, subphase=label)
    _advance_substep(showcase_state)
    return _stage_result("queued", reason)


def _queue_type_action(
    context,
    showcase_state: Dict[str, Any],
    step_slug: str,
    *,
    text: str,
    label: str,
    reason: str,
) -> Dict[str, Any]:
    def callback(action_name: str) -> None:
        context.browser.type_text(text, name=action_name, cooldown_ms=0, reason=reason)

    _queue_browser_action(context, showcase_state, step_slug, label, reason, callback, subphase=label)
    _advance_substep(showcase_state)
    return _stage_result("queued", reason)


def _queue_key_action(
    context,
    showcase_state: Dict[str, Any],
    step_slug: str,
    *,
    kind: str,
    key: str,
    code: str,
    label: str,
    reason: str,
) -> Dict[str, Any]:
    def callback(action_name: str) -> None:
        method = getattr(context.browser, kind)
        method(key, code=code, name=action_name, cooldown_ms=0, reason=reason)

    _queue_browser_action(context, showcase_state, step_slug, label, reason, callback, subphase=label)
    _advance_substep(showcase_state)
    return _stage_result("queued", reason)


def _queue_scroll_action(
    context,
    showcase_state: Dict[str, Any],
    step_slug: str,
    *,
    center: Tuple[int, int],
    label: str,
    reason: str,
) -> Dict[str, Any]:
    delta_y = 980 if step_slug == "scroll-panel" else 1200

    def callback(action_name: str) -> None:
        context.browser.scroll(*center, delta_y=delta_y, name=action_name, cooldown_ms=0, reason=reason)

    _queue_browser_action(context, showcase_state, step_slug, label, reason, callback, subphase=label)
    return _stage_result("queued", reason)


def _begin_proof_wait(showcase_state: Dict[str, Any], step_slug: str) -> Dict[str, Any]:
    showcase_state["waiting_for"] = "proof"
    showcase_state["subphase"] = "proof"
    showcase_state["wait_reason"] = ""
    showcase_state["wait_since_monotonic"] = 0.0
    return _stage_result("running", f"All {STEP_LABELS[step_slug]} actions were dispatched. Waiting for visual proof.")


def _wait_for_visual_proof(context, showcase_state: Dict[str, Any], markers: Dict[str, Any], step_slug: str) -> Dict[str, Any]:
    if markers.get("proof_complete") is not None:
        showcase_state["waiting_for"] = ""
        showcase_state["subphase"] = "proof_complete"
        showcase_state["wait_reason"] = ""
        showcase_state["wait_since_monotonic"] = 0.0
        return _stage_result("stage_complete", f"OpenCV confirmed the {STEP_LABELS[step_slug]} proof beacon turned green.")

    if step_slug in {"scroll-panel", "page-scroll"}:
        centers, result = _require_markers(showcase_state, markers, step_slug, ["primary"])
        if result is not None:
            return result

        # The scroll steps repeat the same wheel action until the green proof beacon appears.
        return _queue_scroll_action(
            context,
            showcase_state,
            step_slug,
            center=centers["primary"],
            label=f"{step_slug}_scroll_retry",
            reason=f"Scroll again inside {STEP_LABELS[step_slug]} until the proof beacon turns green.",
        )

    return _wait_with_timeout(
        showcase_state,
        f"Waiting for the {STEP_LABELS[step_slug]} proof beacon to turn green.",
        subphase="proof",
    )


def _metadata_payload(
    context,
    showcase_state: Dict[str, Any],
    markers: Dict[str, Any],
    *,
    status: str,
    note: str,
    missing_markers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    step_index = min(int(showcase_state.get("step_index", 0)), len(STEP_ORDER) - 1)
    step_slug = STEP_ORDER[step_index]
    return {
        "interaction_showcase": {
            "status": status,
            "step_index": step_index,
            "step_slug": step_slug,
            "step_label": STEP_LABELS[step_slug],
            "step_count": len(STEP_ORDER),
            "phase": showcase_state.get("phase", "running"),
            "subphase": showcase_state.get("subphase", ""),
            "substep_index": int(showcase_state.get("substep_index", 0)),
            "visible_step": markers.get("visible_step"),
            "pending_action_name": showcase_state.get("pending_action_name", ""),
            "waiting_reason": showcase_state.get("wait_reason", ""),
            "note": note,
            "missing_markers": missing_markers or [],
            "frame_index": context.frame_index,
            "marker_debug": _build_marker_debug(markers),
        }
    }


# Stage 1: move into the pointer pad, press, hold briefly, and release.
def run_pointer_stage(context, showcase_state: Dict[str, Any], markers: Dict[str, Any]) -> Dict[str, Any]:
    visible = _require_stage_visible(showcase_state, markers, "pointer", ["primary"])
    if visible is not None:
        return visible

    if showcase_state.get("waiting_for") == "proof":
        return _wait_for_visual_proof(context, showcase_state, markers, "pointer")

    centers, result = _require_markers(showcase_state, markers, "pointer", ["primary"])
    if result is not None:
        return result

    primary = centers["primary"]
    substep = int(showcase_state.get("substep_index", 0))
    if substep == 0:
        # The blue marker sits in the middle of the pointer pad, so moving to it demonstrates targeting.
        return _queue_point_action(
            context,
            showcase_state,
            "pointer",
            kind="move",
            point=primary,
            label="pointer_move",
            reason="Move to the pointer-pad marker found in the frame.",
        )
    if substep == 1:
        return _queue_point_action(
            context,
            showcase_state,
            "pointer",
            kind="mouse_down",
            point=primary,
            label="pointer_down",
            reason="Press inside the pointer pad at the detected marker.",
        )
    if substep == 2:
        return _queue_pause_action(
            context,
            showcase_state,
            "pointer",
            duration_ms=POINTER_HOLD_MS,
            label="pointer_hold",
            reason="Hold the pointer press briefly so students can see the pressed state.",
        )
    if substep == 3:
        return _queue_point_action(
            context,
            showcase_state,
            "pointer",
            kind="mouse_up",
            point=primary,
            label="pointer_up",
            reason="Release inside the pointer pad to finish the pointer stage.",
        )
    return _begin_proof_wait(showcase_state, "pointer")


# Stage 2: use two different gestures on two different markers on the same panel.
def run_clicks_stage(context, showcase_state: Dict[str, Any], markers: Dict[str, Any]) -> Dict[str, Any]:
    visible = _require_stage_visible(showcase_state, markers, "clicks", ["primary", "secondary"])
    if visible is not None:
        return visible

    if showcase_state.get("waiting_for") == "proof":
        return _wait_for_visual_proof(context, showcase_state, markers, "clicks")

    centers, result = _require_markers(showcase_state, markers, "clicks", ["primary", "secondary"])
    if result is not None:
        return result

    substep = int(showcase_state.get("substep_index", 0))
    if substep == 0:
        return _queue_point_action(
            context,
            showcase_state,
            "clicks",
            kind="click",
            point=centers["primary"],
            label="single_click",
            reason="Single-click the first click target at the detected primary marker.",
        )
    if substep == 1:
        return _queue_point_action(
            context,
            showcase_state,
            "clicks",
            kind="double_click",
            point=centers["secondary"],
            label="double_click",
            reason="Double-click the second click target at the detected secondary marker.",
        )
    return _begin_proof_wait(showcase_state, "clicks")


# Stage 3: drag from the launch marker to the dock marker and wait for the dock proof.
def run_drag_stage(context, showcase_state: Dict[str, Any], markers: Dict[str, Any]) -> Dict[str, Any]:
    visible = _require_stage_visible(showcase_state, markers, "drag", ["primary", "secondary"])
    if visible is not None:
        return visible

    if showcase_state.get("waiting_for") == "proof":
        return _wait_for_visual_proof(context, showcase_state, markers, "drag")

    # After the drag fires, the source marker can disappear because the token moved into the dock.
    if int(showcase_state.get("substep_index", 0)) >= 1:
        return _begin_proof_wait(showcase_state, "drag")

    centers, result = _require_markers(showcase_state, markers, "drag", ["primary", "secondary"])
    if result is not None:
        return result

    substep = int(showcase_state.get("substep_index", 0))
    if substep == 0:
        # The primary marker is on the token, and the secondary marker is inside the dock.
        return _queue_drag_action(
            context,
            showcase_state,
            "drag",
            start=centers["primary"],
            end=centers["secondary"],
            label="drag_token_to_dock",
            reason="Drag the token from the detected start marker into the detected dock marker.",
        )
    return _begin_proof_wait(showcase_state, "drag")


# Stage 4: spin the wheel inside the inner panel until the scroll proof beacon turns green.
def run_scroll_panel_stage(context, showcase_state: Dict[str, Any], markers: Dict[str, Any]) -> Dict[str, Any]:
    visible = _require_stage_visible(showcase_state, markers, "scroll-panel", ["primary"])
    if visible is not None:
        return visible

    if showcase_state.get("waiting_for") == "proof":
        return _wait_for_visual_proof(context, showcase_state, markers, "scroll-panel")

    centers, result = _require_markers(showcase_state, markers, "scroll-panel", ["primary"])
    if result is not None:
        return result

    substep = int(showcase_state.get("substep_index", 0))
    if substep == 0:
        showcase_state["waiting_for"] = "proof"
        showcase_state["subphase"] = "scroll_panel_start"
        _advance_substep(showcase_state)
        return _queue_scroll_action(
            context,
            showcase_state,
            "scroll-panel",
            center=centers["primary"],
            label="scroll_panel_start",
            reason="Scroll inside the detected inner scroll panel.",
        )
    return _wait_for_visual_proof(context, showcase_state, markers, "scroll-panel")


# Stage 5: scroll the document itself at the page marker until the page proof flips.
def run_page_scroll_stage(context, showcase_state: Dict[str, Any], markers: Dict[str, Any]) -> Dict[str, Any]:
    visible = _require_stage_visible(showcase_state, markers, "page-scroll", ["primary"])
    if visible is not None:
        return visible

    if showcase_state.get("waiting_for") == "proof":
        return _wait_for_visual_proof(context, showcase_state, markers, "page-scroll")

    centers, result = _require_markers(showcase_state, markers, "page-scroll", ["primary"])
    if result is not None:
        return result

    substep = int(showcase_state.get("substep_index", 0))
    if substep == 0:
        showcase_state["waiting_for"] = "proof"
        showcase_state["subphase"] = "page_scroll_start"
        _advance_substep(showcase_state)
        return _queue_scroll_action(
            context,
            showcase_state,
            "page-scroll",
            center=centers["primary"],
            label="page_scroll_start",
            reason="Scroll the document at the detected page-scroll runway marker.",
        )
    return _wait_for_visual_proof(context, showcase_state, markers, "page-scroll")


# Stage 6: focus the input, type text, then focus the textarea and type again.
def run_text_entry_stage(context, showcase_state: Dict[str, Any], markers: Dict[str, Any]) -> Dict[str, Any]:
    visible = _require_stage_visible(showcase_state, markers, "text-entry", ["primary", "secondary"])
    if visible is not None:
        return visible

    if showcase_state.get("waiting_for") == "proof":
        return _wait_for_visual_proof(context, showcase_state, markers, "text-entry")

    centers, result = _require_markers(showcase_state, markers, "text-entry", ["primary", "secondary"])
    if result is not None:
        return result

    substep = int(showcase_state.get("substep_index", 0))
    if substep == 0:
        return _queue_point_action(
            context,
            showcase_state,
            "text-entry",
            kind="click",
            point=centers["primary"],
            label="focus_input",
            reason="Focus the text input at the detected primary marker.",
        )
    if substep == 1:
        return _queue_type_action(
            context,
            showcase_state,
            "text-entry",
            text=TEXT_INPUT_VALUE,
            label="type_input",
            reason="Type the short proof string into the input field.",
        )
    if substep == 2:
        return _queue_point_action(
            context,
            showcase_state,
            "text-entry",
            kind="click",
            point=centers["secondary"],
            label="focus_textarea",
            reason="Focus the textarea at the detected secondary marker.",
        )
    if substep == 3:
        return _queue_type_action(
            context,
            showcase_state,
            "text-entry",
            text=TEXT_AREA_VALUE,
            label="type_textarea",
            reason="Type the multi-line proof string into the textarea.",
        )
    return _begin_proof_wait(showcase_state, "text-entry")


# Stage 7: focus the keyboard stage, then send down, up, and press events in sequence.
def run_keyboard_stage(context, showcase_state: Dict[str, Any], markers: Dict[str, Any]) -> Dict[str, Any]:
    visible = _require_stage_visible(showcase_state, markers, "keyboard", ["primary"])
    if visible is not None:
        return visible

    if showcase_state.get("waiting_for") == "proof":
        return _wait_for_visual_proof(context, showcase_state, markers, "keyboard")

    centers, result = _require_markers(showcase_state, markers, "keyboard", ["primary"])
    if result is not None:
        return result

    primary = centers["primary"]
    substep = int(showcase_state.get("substep_index", 0))
    if substep == 0:
        return _queue_point_action(
            context,
            showcase_state,
            "keyboard",
            kind="click",
            point=primary,
            label="focus_keyboard",
            reason="Focus the keyboard stage at the detected primary marker.",
        )
    if substep == 1:
        return _queue_key_action(
            context,
            showcase_state,
            "keyboard",
            kind="key_down",
            key="ArrowRight",
            code="ArrowRight",
            label="key_down_arrow_right",
            reason="Send a key-down event so students can see a held key state.",
        )
    if substep == 2:
        return _queue_key_action(
            context,
            showcase_state,
            "keyboard",
            kind="key_up",
            key="ArrowRight",
            code="ArrowRight",
            label="key_up_arrow_right",
            reason="Release ArrowRight to finish the held-key example.",
        )
    if substep == 3:
        return _queue_key_action(
            context,
            showcase_state,
            "keyboard",
            kind="key_press",
            key="Enter",
            code="Enter",
            label="key_press_enter",
            reason="Send a quick Enter press as the final keyboard gesture.",
        )
    return _begin_proof_wait(showcase_state, "keyboard")


STAGE_HANDLERS: Dict[str, Callable[[Any, Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = {
    "pointer": run_pointer_stage,
    "clicks": run_clicks_stage,
    "drag": run_drag_stage,
    "scroll-panel": run_scroll_panel_stage,
    "page-scroll": run_page_scroll_stage,
    "text-entry": run_text_entry_stage,
    "keyboard": run_keyboard_stage,
}


def on_frame(image, context):
    if SHOWCASE_URL_TOKEN not in context.url.replace("\\", "/"):
        return {
            "interaction_showcase": {
                "status": "idle",
                "note": "This OpenCV showcase only runs on the local input-lab page.",
                "url": context.url,
            }
        }

    showcase_state = context.state.setdefault(
        "interaction_showcase",
        {
            "step_index": 0,
            "substep_index": 0,
            "phase": "running",
            "subphase": "locate_step",
            "waiting_for": "",
            "pending_action_name": "",
            "pending_action_label": "",
            "pending_action_reason": "",
            "action_serial": 0,
            "wait_reason": "",
            "wait_since_monotonic": 0.0,
            "observe_until_monotonic": 0.0,
            "last_navigation_attempt_monotonic": 0.0,
            "blocked_reason": "",
            "blocked_result": {},
        },
    )

    frame_bgr = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    markers = detect_markers(frame_bgr)
    step_index = min(int(showcase_state.get("step_index", 0)), len(STEP_ORDER) - 1)
    current_step = STEP_ORDER[step_index]
    now = time.monotonic()

    if showcase_state.get("phase") == "blocked":
        return _metadata_payload(
            context,
            showcase_state,
            markers,
            status="blocked",
            note=str(showcase_state.get("blocked_reason") or "The showcase is blocked."),
        )

    if showcase_state.get("phase") == "complete":
        return _metadata_payload(
            context,
            showcase_state,
            markers,
            status="complete",
            note="The OpenCV showcase completed the full wizard and left the proof visible.",
        )

    pending = _resolve_pending_action(context, showcase_state)
    if pending is not None:
        if pending["status"] == "blocked":
            return _metadata_payload(
                context,
                showcase_state,
                markers,
                status="blocked",
                note=str(pending["reason"]),
            )
        if pending["status"] == "waiting":
            return _metadata_payload(
                context,
                showcase_state,
                markers,
                status="waiting",
                note=str(pending["reason"]),
            )

    if showcase_state.get("phase") == "observing":
        showcase_state["subphase"] = "observe"
        observe_until = float(showcase_state.get("observe_until_monotonic", 0.0))
        if now < observe_until:
            remaining = max(0.0, observe_until - now)
            _note_wait(
                showcase_state,
                f"Observing the completed {STEP_LABELS[current_step]} stage for {remaining:.1f} more seconds.",
                subphase="observe",
            )
            return _metadata_payload(
                context,
                showcase_state,
                markers,
                status="waiting",
                note=f"Observing the completed {STEP_LABELS[current_step]} stage.",
            )

        showcase_state["wait_reason"] = ""
        showcase_state["wait_since_monotonic"] = 0.0
        if step_index >= len(STEP_ORDER) - 1:
            showcase_state["phase"] = "complete"
            showcase_state["subphase"] = "complete"
            return _metadata_payload(
                context,
                showcase_state,
                markers,
                status="complete",
                note="The OpenCV showcase completed the full wizard and left the proof visible.",
            )
        showcase_state["phase"] = "navigating"
        showcase_state["subphase"] = "navigate"
        showcase_state["last_navigation_attempt_monotonic"] = 0.0

    if showcase_state.get("phase") == "navigating":
        expected_next = STEP_ORDER[step_index + 1]
        if float(showcase_state.get("last_navigation_attempt_monotonic", 0.0)) > 0.0:
            showcase_state["step_index"] = step_index + 1
            showcase_state["substep_index"] = 0
            showcase_state["phase"] = "running"
            showcase_state["subphase"] = "locate_step"
            showcase_state["waiting_for"] = ""
            showcase_state["wait_reason"] = ""
            showcase_state["wait_since_monotonic"] = 0.0
            showcase_state["last_navigation_attempt_monotonic"] = 0.0
            return _metadata_payload(
                context,
                showcase_state,
                markers,
                status="running",
                note=f"Advanced to {STEP_LABELS[expected_next]}. Waiting for its markers to settle on screen.",
            )

        next_center = _marker_center(markers, "next")
        if next_center is None:
            result = _wait_with_timeout(
                showcase_state,
                "Waiting for the Next button fiducial while navigating to the next stage.",
                missing_markers=["next"],
                subphase="navigate",
            )
            return _metadata_payload(
                context,
                showcase_state,
                markers,
                status=result["status"],
                note=result["note"],
                missing_markers=result["missing_markers"],
            )

        if now - float(showcase_state.get("last_navigation_attempt_monotonic", 0.0)) < NAVIGATION_RETRY_SECONDS:
            _note_wait(
                showcase_state,
                f"Waiting for {STEP_LABELS[expected_next]} to appear after clicking Next.",
                subphase="navigate",
            )
            return _metadata_payload(
                context,
                showcase_state,
                markers,
                status="waiting",
                note=f"Waiting for {STEP_LABELS[expected_next]} to appear.",
            )

        showcase_state["last_navigation_attempt_monotonic"] = now
        result = _queue_point_action(
            context,
            showcase_state,
            current_step,
            kind="click",
            point=next_center,
            label="next_button",
            reason=f"Advance from {STEP_LABELS[current_step]} to {STEP_LABELS[expected_next]} using the Next button marker.",
            advance_substep=False,
        )
        return _metadata_payload(
            context,
            showcase_state,
            markers,
            status=result["status"],
            note=result["note"],
        )

    stage_handler = STAGE_HANDLERS[current_step]
    stage_result = stage_handler(context, showcase_state, markers)
    if stage_result["status"] == "stage_complete":
        showcase_state["phase"] = "observing"
        showcase_state["subphase"] = "observe"
        showcase_state["observe_until_monotonic"] = now + OBSERVATION_SECONDS
        showcase_state["wait_reason"] = ""
        showcase_state["wait_since_monotonic"] = 0.0
        return _metadata_payload(
            context,
            showcase_state,
            markers,
            status="running",
            note=stage_result["note"],
        )

    return _metadata_payload(
        context,
        showcase_state,
        markers,
        status=stage_result["status"],
        note=stage_result["note"],
        missing_markers=stage_result.get("missing_markers"),
    )


app = BrowserApp(
    start_target="game://input-lab",
    fps=5.0,
    on_frame=on_frame,
)
