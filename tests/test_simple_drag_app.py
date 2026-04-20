from __future__ import annotations

import importlib.util
import unittest
from types import SimpleNamespace
from typing import Any, Dict, List

from test_support import ROOT_DIR
from webvisionkit.deps import cv2, np


MODULE_PATH = ROOT_DIR / "apps" / "simple_drag" / "app.py"


def load_simple_drag_module():
    spec = importlib.util.spec_from_file_location("test_simple_drag_app_module", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BrowserSpy:
    def __init__(self) -> None:
        self.drags: List[Dict[str, Any]] = []

    def drag(self, x: int, y: int, end_x: int, end_y: int, **kwargs: Any) -> None:
        self.drags.append(
            {
                "x": x,
                "y": y,
                "end_x": end_x,
                "end_y": end_y,
                "kwargs": kwargs,
            }
        )


def make_context(frame_index: int = 1):
    browser = BrowserSpy()
    context = SimpleNamespace(
        state={},
        browser=browser,
        frame_index=frame_index,
    )
    return context, browser


def make_frame(block_box=None):
    image = np.full((420, 860, 3), 229, dtype=np.uint8)

    goal_x, goal_y, goal_w, goal_h = (560, 120, 170, 170)
    image[goal_y:goal_y + goal_h, goal_x:goal_x + goal_w] = (76, 177, 34)

    if block_box is not None:
        block_x, block_y, block_w, block_h = block_box
        image[block_y:block_y + block_h, block_x:block_x + block_w] = (48, 59, 255)

    return image


@unittest.skipUnless(np is not None and cv2 is not None, "simple_drag vision tests require numpy and cv2")
class SimpleDragAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_simple_drag_module()

    def test_unsolved_frame_queues_one_drag(self) -> None:
        context, browser = make_context(frame_index=1)
        image = make_frame(block_box=(120, 160, 82, 82))

        result = self.module.on_frame(image, context)
        payload = result["simple_drag_bot"]

        self.assertEqual(payload["status"], "drag_queued")
        self.assertFalse(payload["won"])
        self.assertTrue(payload["drag_queued"])
        self.assertEqual(payload["attempt_count"], 1)
        self.assertEqual(len(browser.drags), 1)
        self.assertEqual(context.state["attempt_count"], 1)
        self.assertEqual(context.state["last_drag_frame"], 1)

    def test_solved_frame_detects_win_without_dragging(self) -> None:
        context, browser = make_context(frame_index=4)
        image = make_frame(block_box=(604, 164, 82, 82))

        result = self.module.on_frame(image, context)
        payload = result["simple_drag_bot"]

        self.assertEqual(payload["status"], "won")
        self.assertTrue(payload["won"])
        self.assertFalse(payload["drag_queued"])
        self.assertEqual(payload["attempt_count"], 0)
        self.assertEqual(browser.drags, [])
        self.assertTrue(context.state["won"])


if __name__ == "__main__":
    unittest.main()
