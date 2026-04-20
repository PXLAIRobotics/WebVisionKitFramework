from __future__ import annotations

import json
import socket
from typing import Any, Dict, Optional

from .cdp import CDPClient, WebSocketBadStatusException
from .deps import requests
from .errors import ChromeProbeError, RecoverableStreamError
from .models import StreamConfig, TargetState
from .targets import clear_current_target, connect_browser_client, get_browser_ws_url_via_http, resolve_page_target


def _print_probe(stage: str, message: str) -> None:
    print(f"[probe] {stage}: {message}")


def probe_host_endpoint(config: StreamConfig) -> None:
    try:
        socket.create_connection((config.chrome_host, config.chrome_port), timeout=2.0).close()
    except OSError as exc:
        raise ChromeProbeError(
            "host",
            f"Could not reach {config.chrome_host}:{config.chrome_port} from the container. Ensure Chrome is running on the host and reachable from Docker.",
        ) from exc
    _print_probe("host", f"reachable at {config.chrome_host}:{config.chrome_port}")


def probe_version_endpoint(config: StreamConfig, target_state: TargetState) -> Dict[str, Any]:
    if requests is None:
        raise ChromeProbeError("http", "requests is not installed inside the container.")

    try:
        response = requests.get(config.json_version_url, timeout=2)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        if target_state.browser_ws_url:
            _print_probe(
                "http",
                f"{config.json_version_url} was unavailable from the container; continuing with the launcher-provided browser websocket.",
            )
            return {}
        raise ChromeProbeError(
            "http",
            f"Could not fetch {config.json_version_url}. Ensure Chrome was started with --remote-debugging-port={config.chrome_port}.",
        ) from exc

    if not isinstance(payload, dict):
        raise ChromeProbeError("http", f"{config.json_version_url} did not return a JSON object.")

    _print_probe("http", f"DevTools version endpoint responded at {config.json_version_url}")
    return payload


def probe_browser_websocket(config: StreamConfig, target_state: TargetState, version_data: Dict[str, Any]) -> None:
    if not target_state.browser_ws_url:
        browser_ws_url = str(version_data.get("webSocketDebuggerUrl") or "").strip()
        if not browser_ws_url:
            raise ChromeProbeError("browser-ws", "DevTools version data did not include webSocketDebuggerUrl.")
        target_state.browser_ws_url = browser_ws_url

    browser_client: Optional[CDPClient] = None
    try:
        browser_client = connect_browser_client(config, target_state)
        browser_client.call("Target.getTargets")
    except RecoverableStreamError as exc:
        target_state.browser_ws_url = ""
        raise ChromeProbeError(
            "browser-ws",
            "Connected to DevTools HTTP, but could not open or validate the browser websocket.",
        ) from exc
    finally:
        if browser_client is not None:
            browser_client.close()

    _print_probe("browser-ws", "browser websocket validated with Target.getTargets")


def probe_and_connect_page_client(config: StreamConfig, target_state: TargetState) -> CDPClient:
    probe_host_endpoint(config)
    version_data = probe_version_endpoint(config, target_state)

    if not target_state.browser_ws_url:
        target_state.browser_ws_url = get_browser_ws_url_via_http(config)

    probe_browser_websocket(config, target_state, version_data)

    try:
        resolve_page_target(config, target_state)
    except RecoverableStreamError as exc:
        clear_current_target(target_state, invalidate_initial_hint=True)
        raise ChromeProbeError(
            "page-target",
            "DevTools is reachable, but the framework could not create or select a usable page target.",
        ) from exc

    try:
        client = CDPClient(target_state.current_page_ws_url, receive_timeout_seconds=config.receive_timeout_seconds)
    except WebSocketBadStatusException as exc:
        clear_current_target(target_state, invalidate_initial_hint=True)
        raise ChromeProbeError(
            "page-ws",
            "A page target was selected, but its websocket was stale or unavailable. The framework will retry with fresh target discovery.",
        ) from exc
    except OSError as exc:
        clear_current_target(target_state, invalidate_initial_hint=True)
        raise ChromeProbeError(
            "page-ws",
            "A page target was selected, but the framework could not open the page websocket.",
        ) from exc

    _print_probe("page-ws", f"connected to page websocket {target_state.current_page_ws_url}")
    return client
