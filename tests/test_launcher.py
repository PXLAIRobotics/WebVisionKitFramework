from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from test_support import ROOT_DIR


class LauncherFunctionTests(unittest.TestCase):
    def run_bash(self, body: str) -> str:
        command = f'cd "{ROOT_DIR}" && WEBVISIONKIT_SOURCE_ONLY=1 source ./launch.bash && {body}'
        completed = subprocess.run(
            ["bash", "-lc", command],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    def test_target_resolution_maps_game_tokens_to_file_urls(self) -> None:
        resolved = self.run_bash('discover_game_slugs >/dev/null; resolve_target_value "game://input-lab"')
        expected = f"file://{ROOT_DIR}/games/input-lab/index.html"
        self.assertEqual(resolved, expected)

    def test_default_output_dir_is_repo_relative(self) -> None:
        resolved = self.run_bash('OUTPUT_DIR_RAW=""; resolve_output_layout; printf "%s\\n" "${HOST_OUTPUT_DIR}"')
        self.assertEqual(resolved, f"{ROOT_DIR}/output")


if __name__ == "__main__":
    unittest.main()
