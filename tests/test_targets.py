from __future__ import annotations

import unittest

from test_support import ROOT_DIR  # noqa: F401
from webvisionkit.targets import rewrite_ws_host


class TargetUtilityTests(unittest.TestCase):
    def test_rewrite_ws_host_updates_host_and_port(self) -> None:
        rewritten = rewrite_ws_host(
            "ws://127.0.0.1:9222/devtools/page/example-target",
            "host.docker.internal",
            9333,
        )
        self.assertEqual(
            rewritten,
            "ws://host.docker.internal:9333/devtools/page/example-target",
        )


if __name__ == "__main__":
    unittest.main()
