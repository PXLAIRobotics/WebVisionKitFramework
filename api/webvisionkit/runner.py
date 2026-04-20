from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from .apps import inspect_app_definition, load_app
from .config import parse_args
from .deps import ensure_runtime_dependencies
from .errors import FatalStreamError
from .runtime import install_signal_handlers, run_loaded_app, run_stream


def build_runner_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--inspect-app", action="store_true")
    return parser


def resolve_effective_start_target(app_start_target: str, app_default_target_url: str, target_url_override: str) -> str:
    candidate = target_url_override.strip() or app_default_target_url.strip() or app_start_target.strip()
    if not candidate:
        raise FatalStreamError("No start target is available for the selected app.")
    if candidate.startswith("game://"):
        raise FatalStreamError(
            f"Unresolved game target {candidate!r}. Launch apps through ./launch.bash so the host-side launcher can resolve local game paths."
        )
    return candidate


def main(argv: Optional[Sequence[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    try:
        install_signal_handlers()
        runner_args, remaining = build_runner_parser().parse_known_args(argv)
        config = parse_args(remaining)
        ensure_runtime_dependencies()

        if runner_args.inspect_app:
            definition = inspect_app_definition(config)
            print(json.dumps(definition, sort_keys=True))
            return 0

        loaded_app = load_app(config)
        config.start_target_url = resolve_effective_start_target(
            loaded_app.definition.start_target,
            config.app_default_target_url,
            config.target_url_override,
        )
        return run_loaded_app(config, loaded_app)
    except KeyboardInterrupt:
        print("\n[info] Stopping.")
        return 130
    except FatalStreamError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
