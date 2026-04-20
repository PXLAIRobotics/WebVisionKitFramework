from __future__ import annotations

import unittest

from test_support import make_stream_config, make_target_state
from webvisionkit.actions import execute_operations
from webvisionkit.models import InteractionState


class UnusedClient:
    def call(self, *_args, **_kwargs):
        raise AssertionError("dry-run action execution should not call the CDP client")


class ActionExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = make_stream_config(action_mode="dry-run", action_default_cooldown_ms=500)
        self.target_state = make_target_state()
        self.interaction_state = InteractionState()
        self.interaction_state.viewport.frame_width = 300
        self.interaction_state.viewport.frame_height = 200
        self.interaction_state.viewport.css_viewport_width = 300
        self.interaction_state.viewport.css_viewport_height = 200
        self.client = UnusedClient()

    def test_invalid_coordinates_are_rejected(self) -> None:
        requested, results = execute_operations(
            self.client,
            self.config,
            "unit-test",
            self.interaction_state,
            self.target_state,
            [{"type": "click", "x": 301, "y": 50}],
        )

        self.assertEqual(len(requested), 1)
        self.assertEqual(results[0]["status"], "invalid")
        self.assertIn("outside the current frame width", results[0]["message"])

    def test_cooldown_skips_repeated_actions(self) -> None:
        action = {"type": "click", "x": 120, "y": 80, "name": "cell-center"}
        _, first_results = execute_operations(
            self.client,
            self.config,
            "unit-test",
            self.interaction_state,
            self.target_state,
            [action],
        )
        _, second_results = execute_operations(
            self.client,
            self.config,
            "unit-test",
            self.interaction_state,
            self.target_state,
            [action],
        )

        self.assertEqual(first_results[0]["status"], "dry_run")
        self.assertEqual(second_results[0]["status"], "skipped_cooldown")


if __name__ == "__main__":
    unittest.main()
