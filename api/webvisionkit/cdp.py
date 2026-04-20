from __future__ import annotations

import json
import time
from collections import deque
from typing import Any, Deque, Dict, Optional

from .deps import (
    WebSocketBadStatusException,
    WebSocketConnectionClosedException,
    WebSocketTimeoutException,
    websocket,
)
from .errors import RecoverableStreamError


class CDPClient:
    def __init__(self, ws_url: str, receive_timeout_seconds: float) -> None:
        if websocket is None:
            raise RecoverableStreamError("websocket-client is not installed inside the container.")

        self.ws_url = ws_url
        self.receive_timeout_seconds = receive_timeout_seconds
        self.ws = websocket.create_connection(ws_url, timeout=10)
        self.ws.settimeout(receive_timeout_seconds)
        self.next_id = 1
        self.pending_messages: Deque[Dict[str, Any]] = deque()

    def send_cmd(self, method: str, params: Optional[Dict[str, Any]] = None) -> int:
        msg_id = self.next_id
        self.next_id += 1
        payload = {
            "id": msg_id,
            "method": method,
            "params": params or {},
        }
        self.ws.send(json.dumps(payload))
        return msg_id

    def _recv_from_socket(self) -> Dict[str, Any]:
        raw = self.ws.recv()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    def call(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 10.0) -> Dict[str, Any]:
        msg_id = self.send_cmd(method, params)
        deadline = time.monotonic() + timeout

        while True:
            try:
                msg = self._recv_from_socket()
            except WebSocketTimeoutException as exc:
                if time.monotonic() >= deadline:
                    raise RecoverableStreamError(f"Timed out waiting for CDP response to {method}") from exc
                continue

            if msg.get("id") == msg_id:
                if "error" in msg:
                    raise RecoverableStreamError(f"CDP command {method} failed: {msg['error']}")
                return msg.get("result", {})

            self.pending_messages.append(msg)
            if time.monotonic() >= deadline:
                raise RecoverableStreamError(f"Timed out waiting for CDP response to {method}")

    def recv_event(self) -> Dict[str, Any]:
        if self.pending_messages:
            return self.pending_messages.popleft()
        return self._recv_from_socket()

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass


__all__ = [
    "CDPClient",
    "WebSocketBadStatusException",
    "WebSocketConnectionClosedException",
    "WebSocketTimeoutException",
]
