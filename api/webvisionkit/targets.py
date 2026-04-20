from __future__ import annotations

import json
import sys
import time
from typing import Any, Dict, List, Optional

from .cdp import CDPClient, WebSocketBadStatusException
from .deps import requests
from .errors import RecoverableStreamError
from .models import StreamConfig, TargetState


def rewrite_ws_host(ws_url: str, new_host: str, new_port: int) -> str:
    normalized = ws_url.strip().replace("\\/", "/")
    if not normalized:
        return ""
    prefix, sep, remainder = normalized.partition("://")
    if not sep:
        return normalized

    host_and_path = remainder.split("/", 1)
    host_port = host_and_path[0]
    path = host_and_path[1] if len(host_and_path) > 1 else ""
    if ":" in host_port:
        _, _, host_remainder = host_port.partition(":")
        if not host_remainder.isdigit():
            new_host_port = f"{new_host}:{new_port}"
        else:
            new_host_port = f"{new_host}:{new_port}"
    else:
        new_host_port = f"{new_host}:{new_port}"

    rebuilt = f"{prefix}://{new_host_port}"
    if path:
        rebuilt = f"{rebuilt}/{path}"
    return rebuilt


def interruptible_sleep(seconds: float, step: float = 0.25) -> None:
    deadline = time.monotonic() + max(0.0, seconds)
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(step, remaining))


def build_target_state(config: StreamConfig) -> TargetState:
    browser_ws_url = ""
    if config.browser_browser_ws_url:
        browser_ws_url = rewrite_ws_host(config.browser_browser_ws_url, config.chrome_host, config.chrome_port)

    initial_page_ws_url = ""
    if config.browser_ws_url:
        initial_page_ws_url = rewrite_ws_host(config.browser_ws_url, config.chrome_host, config.chrome_port)

    last_known_url = config.start_target_url.strip()
    return TargetState(
        browser_ws_url=browser_ws_url,
        initial_page_ws_url=initial_page_ws_url,
        initial_page_ws_url_valid=bool(initial_page_ws_url),
        startup_target_pending=config.startup_target_mode == "new-target",
        last_known_url=last_known_url,
        pending_navigation_url="" if config.startup_target_mode == "new-target" else last_known_url,
    )


def extract_target_id_from_ws_url(ws_url: str) -> str:
    normalized = ws_url.strip().replace("\\/", "/")
    marker = "/devtools/page/"
    if marker not in normalized:
        return ""
    return normalized.rsplit("/", 1)[-1]


def is_missing_target_error(exc: BaseException) -> bool:
    return "No such target id" in str(exc)


def get_target_id(target: Dict[str, Any]) -> str:
    target_id = str(target.get("id") or target.get("targetId") or "").strip()
    if target_id:
        return target_id
    return extract_target_id_from_ws_url(str(target.get("webSocketDebuggerUrl") or ""))


def note_last_known_url(target_state: TargetState, url: str) -> None:
    normalized = url.strip()
    if normalized:
        target_state.last_known_url = normalized


def clear_current_target(target_state: TargetState, invalidate_initial_hint: bool = False) -> None:
    target_state.current_page_ws_url = ""
    target_state.current_target_id = ""
    target_state.current_target_title = ""
    target_state.current_target_url = ""
    if invalidate_initial_hint:
        target_state.initial_page_ws_url_valid = False


def build_page_target(config: StreamConfig, target_id: str) -> Dict[str, Any]:
    ws_url = f"ws://{config.chrome_host}:{config.chrome_port}/devtools/page/{target_id}"
    return {
        "id": target_id,
        "targetId": target_id,
        "type": "page",
        "title": "",
        "url": "",
        "webSocketDebuggerUrl": ws_url,
    }


def update_target_state_from_target(config: StreamConfig, target_state: TargetState, target: Dict[str, Any]) -> Dict[str, Any]:
    target_id = get_target_id(target)
    updated = build_page_target(config, target_id)
    updated.update(target)
    target_state.current_target_id = target_id
    target_state.current_page_ws_url = rewrite_ws_host(
        str(updated.get("webSocketDebuggerUrl") or ""),
        config.chrome_host,
        config.chrome_port,
    )
    target_state.current_target_title = str(updated.get("title") or "")
    target_state.current_target_url = str(updated.get("url") or "")
    note_last_known_url(target_state, target_state.current_target_url)
    return updated


def find_page_target_by_id(targets: List[Dict[str, Any]], target_id: str) -> Optional[Dict[str, Any]]:
    normalized = target_id.strip()
    if not normalized:
        return None
    for target in targets:
        if get_target_id(target) == normalized:
            return target
    return None


def wait_for_debug_endpoint(config: StreamConfig, retries: int = 5, delay: float = 0.5) -> Optional[Dict[str, Any]]:
    if requests is None:
        raise RecoverableStreamError("requests is not installed inside the container.")

    last_error: Optional[Exception] = None
    for _ in range(retries):
        try:
            response = requests.get(config.json_version_url, timeout=2)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            interruptible_sleep(delay)

    if last_error is not None:
        raise RecoverableStreamError(f"Could not reach Chromium DevTools at {config.json_version_url}: {last_error}")
    return None


def get_browser_ws_url_via_http(config: StreamConfig) -> str:
    version_data = wait_for_debug_endpoint(config)
    browser_ws_url = str((version_data or {}).get("webSocketDebuggerUrl") or "").strip()
    if not browser_ws_url:
        raise RecoverableStreamError(
            f"DevTools at {config.json_version_url} did not return webSocketDebuggerUrl."
        )
    return rewrite_ws_host(browser_ws_url, config.chrome_host, config.chrome_port)


def connect_browser_client(config: StreamConfig, target_state: TargetState) -> CDPClient:
    browser_ws_url = target_state.browser_ws_url.strip() or get_browser_ws_url_via_http(config)
    target_state.browser_ws_url = browser_ws_url
    try:
        client = CDPClient(browser_ws_url, receive_timeout_seconds=config.receive_timeout_seconds)
    except WebSocketBadStatusException as exc:
        target_state.browser_ws_url = ""
        raise RecoverableStreamError(f"Failed to connect to the browser websocket {browser_ws_url}: {exc}") from exc
    except OSError as exc:
        target_state.browser_ws_url = ""
        raise RecoverableStreamError(f"Failed to connect to the browser websocket {browser_ws_url}.") from exc

    return client


def list_targets_via_http(config: StreamConfig) -> List[Dict[str, Any]]:
    if requests is None:
        raise RecoverableStreamError("requests is not installed inside the container.")

    response = requests.get(config.json_list_url, timeout=2)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise RecoverableStreamError(f"DevTools target list at {config.json_list_url} did not return a list.")
    return [dict(item) for item in payload if isinstance(item, dict)]


def list_targets_via_browser(config: StreamConfig, target_state: TargetState) -> List[Dict[str, Any]]:
    browser_client: Optional[CDPClient] = None
    try:
        browser_client = connect_browser_client(config, target_state)
        result = browser_client.call("Target.getTargets")
    finally:
        if browser_client is not None:
            browser_client.close()

    target_infos = result.get("targetInfos")
    if not isinstance(target_infos, list):
        raise RecoverableStreamError("Target.getTargets did not return targetInfos.")

    targets: List[Dict[str, Any]] = []
    for raw_target in target_infos:
        if not isinstance(raw_target, dict):
            continue
        target_id = get_target_id(raw_target)
        if not target_id:
            continue
        targets.append(
            {
                "id": target_id,
                "targetId": target_id,
                "type": raw_target.get("type"),
                "title": raw_target.get("title"),
                "url": raw_target.get("url"),
                "webSocketDebuggerUrl": f"ws://{config.chrome_host}:{config.chrome_port}/devtools/page/{target_id}",
            }
        )
    return targets


def list_targets(config: StreamConfig, target_state: TargetState) -> List[Dict[str, Any]]:
    try:
        return list_targets_via_browser(config, target_state)
    except RecoverableStreamError as browser_exc:
        try:
            return list_targets_via_http(config)
        except Exception as http_exc:
            raise RecoverableStreamError(
                f"Could not discover page targets via browser websocket ({browser_exc}) or HTTP ({http_exc})."
            ) from http_exc


def select_page_target(config: StreamConfig, targets: List[Dict[str, Any]]) -> Dict[str, Any]:
    pages = [
        target for target in targets
        if str(target.get("type") or "") == "page" and str(target.get("webSocketDebuggerUrl") or "").strip()
    ]
    if not pages:
        raise RecoverableStreamError("No live page targets are currently available.")

    if config.target_match:
        for target in pages:
            title = str(target.get("title") or "").lower()
            url = str(target.get("url") or "").lower()
            if config.target_match in title or config.target_match in url:
                return target

    return pages[0]


def get_default_new_target_url(config: StreamConfig, target_state: TargetState) -> str:
    return config.start_target_url.strip() or target_state.last_known_url.strip() or "about:blank"


def wait_for_target_by_id(
    config: StreamConfig,
    target_state: TargetState,
    target_id: str,
    retries: int = 20,
    delay: float = 0.2,
) -> Dict[str, Any]:
    last_error: Optional[Exception] = None

    for _ in range(retries):
        try:
            target = find_page_target_by_id(list_targets(config, target_state), target_id)
            if target is not None:
                return target
        except Exception as exc:
            last_error = exc
        interruptible_sleep(delay)

    if last_error is not None:
        raise RecoverableStreamError(f"Created target {target_id} but could not fetch it: {last_error}")
    raise RecoverableStreamError(f"Created target {target_id} but it never appeared in target discovery.")


def create_page_target(
    config: StreamConfig,
    target_state: TargetState,
    url: str,
    *,
    new_window: bool = False,
) -> Dict[str, Any]:
    browser_client: Optional[CDPClient] = None
    print(f"[info] Opening a new page target at: {url}")

    try:
        browser_client = connect_browser_client(config, target_state)
        params: Dict[str, Any] = {"url": url}
        if new_window:
            params["newWindow"] = True
        result = browser_client.call("Target.createTarget", params)
    finally:
        if browser_client is not None:
            browser_client.close()

    target_id = str(result.get("targetId") or "").strip()
    if not target_id:
        raise RecoverableStreamError(f"Chrome did not return a targetId when opening {url!r}.")

    target = wait_for_target_by_id(config, target_state, target_id)
    update_target_state_from_target(config, target_state, target)
    return target


def ensure_page_target(config: StreamConfig, target_state: TargetState, targets: List[Dict[str, Any]]) -> Dict[str, Any]:
    if target_state.current_target_id:
        current = find_page_target_by_id(targets, target_state.current_target_id)
        if current is not None:
            return current
        clear_current_target(target_state, invalidate_initial_hint=True)

    if target_state.startup_target_pending:
        target_state.startup_target_pending = False
        return create_page_target(config, target_state, get_default_new_target_url(config, target_state), new_window=True)

    if target_state.initial_page_ws_url_valid and target_state.initial_page_ws_url:
        hinted_target_id = extract_target_id_from_ws_url(target_state.initial_page_ws_url)
        hinted_target = find_page_target_by_id(targets, hinted_target_id)
        if hinted_target is not None:
            return hinted_target
        target_state.initial_page_ws_url_valid = False

    try:
        return select_page_target(config, targets)
    except RecoverableStreamError:
        return create_page_target(config, target_state, get_default_new_target_url(config, target_state), new_window=False)


def log_selected_target(target_state: TargetState, target: Dict[str, Any]) -> None:
    print(f"[info] Selected target title: {target_state.current_target_title}")
    print(f"[info] Selected target url:   {target_state.current_target_url}")
    print(f"[info] Page websocket: {target_state.current_page_ws_url}")


def resolve_page_target(config: StreamConfig, target_state: TargetState) -> Dict[str, Any]:
    targets = list_targets(config, target_state)
    target = ensure_page_target(config, target_state, targets)
    target = update_target_state_from_target(config, target_state, target)
    log_selected_target(target_state, target)
    return target


def update_target_state_from_event(target_state: TargetState, message: Dict[str, Any]) -> None:
    method = message.get("method")
    params = message.get("params", {})

    if method == "Page.frameNavigated":
        frame = params.get("frame", {})
        if frame.get("parentId"):
            return
        url = str(frame.get("url") or "")
        target_state.current_target_url = url
        note_last_known_url(target_state, url)
        return

    if method == "Page.navigatedWithinDocument":
        url = str(params.get("url") or "")
        target_state.current_target_url = url
        note_last_known_url(target_state, url)


def prepare_target_after_close(config: StreamConfig, target_state: TargetState) -> None:
    reopen_url = target_state.last_known_url.strip() or config.start_target_url.strip()
    clear_current_target(target_state, invalidate_initial_hint=True)
    target_state.pending_navigation_url = ""

    if reopen_url:
        try:
            create_page_target(config, target_state, reopen_url)
            return
        except RecoverableStreamError as exc:
            print(
                f"[warn] Could not reopen the last known URL {reopen_url!r}: {exc}. Falling back to live target discovery.",
                file=sys.stderr,
            )

    resolve_page_target(config, target_state)
