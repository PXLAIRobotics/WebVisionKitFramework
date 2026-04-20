from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from test_support import make_stream_config
from webvisionkit.apps import discover_apps, load_app


class AppDiscoveryTests(unittest.TestCase):
    def test_discover_apps_finds_app_directories_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "alpha").mkdir()
            (root / "alpha" / "app.py").write_text("app = None\n", encoding="utf-8")
            (root / "notes").mkdir()
            (root / "notes" / "helper.py").write_text("# no app module here\n", encoding="utf-8")

            self.assertEqual(discover_apps(root), ["alpha"])

    def test_load_app_supports_helper_modules_inside_app_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app_dir = root / "example_app"
            app_dir.mkdir()
            (app_dir / "helpers.py").write_text(
                "def build_message():\n    return 'helper-loaded'\n",
                encoding="utf-8",
            )
            (app_dir / "app.py").write_text(
                textwrap.dedent(
                    """
                    from helpers import build_message
                    from webvisionkit import BrowserApp


                    def on_frame(image, context):
                        return {"message": build_message()}


                    app = BrowserApp(
                        start_target="about:blank",
                        fps=1.0,
                        on_frame=on_frame,
                    )
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            config = make_stream_config(apps_dir=str(root), app_name="example_app")
            loaded = load_app(config)
            result = loaded.call(None, None)  # type: ignore[arg-type]

            self.assertEqual(loaded.name, "example_app")
            self.assertEqual(result["message"], "helper-loaded")


if __name__ == "__main__":
    unittest.main()
