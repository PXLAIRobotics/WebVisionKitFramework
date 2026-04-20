from __future__ import annotations

from .errors import FatalStreamError

try:
    import cv2
except ModuleNotFoundError:
    cv2 = None  # type: ignore[assignment]

try:
    import numpy as np
except ModuleNotFoundError:
    np = None  # type: ignore[assignment]

try:
    import requests
except ModuleNotFoundError:
    requests = None  # type: ignore[assignment]

try:
    import websocket
    from websocket import (
        WebSocketBadStatusException,
        WebSocketConnectionClosedException,
        WebSocketTimeoutException,
    )
except ModuleNotFoundError:
    websocket = None  # type: ignore[assignment]

    class WebSocketBadStatusException(Exception):
        pass

    class WebSocketConnectionClosedException(Exception):
        pass

    class WebSocketTimeoutException(Exception):
        pass


def ensure_runtime_dependencies() -> None:
    missing = []

    if cv2 is None:
        missing.append("opencv-python-headless (cv2)")
    if np is None:
        missing.append("numpy")
    if requests is None:
        missing.append("requests")
    if websocket is None:
        missing.append("websocket-client")

    if missing:
        joined = ", ".join(missing)
        raise FatalStreamError(
            f"Missing runtime dependencies: {joined}. Run the framework through Docker using ./launch.bash."
        )
