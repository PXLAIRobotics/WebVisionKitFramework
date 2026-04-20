from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from webvisionkit import BrowserApp
from webvisionkit.deps import cv2, np


Box = Tuple[int, int, int, int]
Point = Tuple[int, int]

DRAG_RETRY_COOLDOWN_FRAMES = 3
MIN_CONTOUR_AREA = 400.0
RED_RANGES = [
    ((0, 120, 120), (10, 255, 255)),
    ((170, 120, 120), (179, 255, 255)),
]
GREEN_RANGES = [
    ((45, 80, 80), (85, 255, 255)),
]


def build_color_mask(hsv_image: np.ndarray, ranges: List[Tuple[np.ndarray, np.ndarray]]) -> np.ndarray:
    ensure_vision_dependencies()
    mask = np.zeros(hsv_image.shape[:2], dtype=np.uint8)
    for lower, upper in ranges:
        mask = cv2.bitwise_or(mask, cv2.inRange(hsv_image, lower, upper))

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    return mask


def find_largest_box(mask: np.ndarray, min_area: float = MIN_CONTOUR_AREA) -> Optional[Box]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best_box: Optional[Box] = None
    best_area = 0.0

    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area or area <= best_area:
            continue
        best_area = area
        x, y, w, h = cv2.boundingRect(contour)
        best_box = (int(x), int(y), int(w), int(h))

    return best_box


def center_of_box(box: Box) -> Point:
    x, y, w, h = box
    return (x + w // 2, y + h // 2)


def point_inside_box(point: Point, box: Box) -> bool:
    x, y = point
    box_x, box_y, box_w, box_h = box
    return box_x <= x <= box_x + box_w and box_y <= y <= box_y + box_h


def box_to_dict(box: Optional[Box]) -> Optional[Dict[str, int]]:
    if box is None:
        return None
    x, y, w, h = box
    return {"x": x, "y": y, "w": w, "h": h}


def point_to_dict(point: Optional[Point]) -> Optional[Dict[str, int]]:
    if point is None:
        return None
    x, y = point
    return {"x": x, "y": y}


def ensure_vision_dependencies() -> None:
    if cv2 is None or np is None:
        raise RuntimeError("simple_drag requires numpy and cv2. Run it through ./launch.bash.")


def analyze_scene(image: np.ndarray) -> Dict[str, Any]:
    ensure_vision_dependencies()
    hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    block_box = find_largest_box(build_color_mask(hsv_image, RED_RANGES))
    goal_box = find_largest_box(build_color_mask(hsv_image, GREEN_RANGES))

    block_center = center_of_box(block_box) if block_box is not None else None
    goal_center = center_of_box(goal_box) if goal_box is not None else None
    won = bool(block_center is not None and goal_box is not None and point_inside_box(block_center, goal_box))

    return {
        "block_box": block_box,
        "goal_box": goal_box,
        "block_center": block_center,
        "goal_center": goal_center,
        "won": won,
    }


def build_metadata(scene: Dict[str, Any], status: str, attempt_count: int, drag_queued: bool) -> Dict[str, Any]:
    return {
        "status": status,
        "won": bool(scene["won"]),
        "drag_queued": drag_queued,
        "attempt_count": attempt_count,
        "block_center": point_to_dict(scene["block_center"]),
        "goal_center": point_to_dict(scene["goal_center"]),
        "block_box": box_to_dict(scene["block_box"]),
        "goal_box": box_to_dict(scene["goal_box"]),
    }


def on_frame(image: np.ndarray, context: Any) -> Dict[str, Any]:
    # This starter bot does three things: find the red block, find the green goal, drag once.
    context.state.setdefault("attempt_count", 0)
    context.state.setdefault("last_drag_frame", -DRAG_RETRY_COOLDOWN_FRAMES)
    context.state.setdefault("won", False)

    scene = analyze_scene(image)
    attempt_count = int(context.state["attempt_count"])
    last_drag_frame = int(context.state["last_drag_frame"])
    drag_queued = False
    status = "waiting_for_scene"

    if scene["block_center"] is None or scene["goal_center"] is None:
        context.state["won"] = False
        return {"simple_drag_bot": build_metadata(scene, status, attempt_count, drag_queued)}

    if scene["won"]:
        context.state["won"] = True
        return {"simple_drag_bot": build_metadata(scene, "won", attempt_count, drag_queued)}

    context.state["won"] = False
    if context.frame_index - last_drag_frame < DRAG_RETRY_COOLDOWN_FRAMES:
        status = "cooldown"
        return {"simple_drag_bot": build_metadata(scene, status, attempt_count, drag_queued)}

    block_x, block_y = scene["block_center"]
    goal_x, goal_y = scene["goal_center"]
    context.browser.drag(block_x, block_y, goal_x, goal_y, name="drag-block-to-goal")
    context.state["attempt_count"] = attempt_count + 1
    context.state["last_drag_frame"] = context.frame_index
    drag_queued = True

    return {
        "simple_drag_bot": build_metadata(scene, "drag_queued", int(context.state["attempt_count"]), drag_queued)
    }


app = BrowserApp(
    start_target="game://simple_drag",
    fps=2.0,
    on_frame=on_frame,
)
