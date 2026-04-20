from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from test_support import ROOT_DIR  # noqa: F401
from webvisionkit.config import parse_args


class ConfigParsingTests(unittest.TestCase):
    def test_parse_args_uses_environment_defaults(self) -> None:
        env = {
            "CHROME_HOST": "docker-host",
            "CHROME_PORT": "9333",
            "APP_NAME": "frame_report",
            "ACTION_MODE": "dry-run",
            "LIVE_PREVIEW": "1",
            "MAX_FRAMES": "7",
        }
        with patch.dict(os.environ, env, clear=False):
            config = parse_args([])

        self.assertEqual(config.chrome_host, "docker-host")
        self.assertEqual(config.chrome_port, 9333)
        self.assertEqual(config.app_name, "frame_report")
        self.assertEqual(config.action_mode, "dry-run")
        self.assertTrue(config.live_preview)
        self.assertEqual(config.max_frames, 7)


if __name__ == "__main__":
    unittest.main()
