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

    def run_bash_capture(self, body: str) -> subprocess.CompletedProcess[str]:
        command = f'cd "{ROOT_DIR}" && WEBVISIONKIT_SOURCE_ONLY=1 source ./launch.bash && {body}'
        return subprocess.run(
            ["bash", "-lc", command],
            capture_output=True,
            text=True,
        )

    def test_target_resolution_maps_game_tokens_to_file_urls(self) -> None:
        resolved = self.run_bash('discover_game_slugs >/dev/null; resolve_target_value "game://input-lab"')
        expected = f"file://{ROOT_DIR}/games/input-lab/index.html"
        self.assertEqual(resolved, expected)

    def test_default_output_dir_is_repo_relative(self) -> None:
        resolved = self.run_bash('OUTPUT_DIR_RAW=""; resolve_output_layout; printf "%s\\n" "${HOST_OUTPUT_DIR}"')
        self.assertEqual(resolved, f"{ROOT_DIR}/output")

    def test_parse_chrome_backend_flag_before_command(self) -> None:
        resolved = self.run_bash(
            """
            parse_launch_args --chrome-backend linux doctor
            printf '%s,%s\\n' "${COMMAND}" "${WSL_CHROME_BACKEND}"
            """
        )
        self.assertEqual(resolved, "doctor,linux")

    def test_parse_chrome_backend_flag_after_command(self) -> None:
        resolved = self.run_bash(
            """
            parse_launch_args chrome --chrome-backend windows
            printf '%s,%s\\n' "${COMMAND}" "${WSL_CHROME_BACKEND}"
            """
        )
        self.assertEqual(resolved, "chrome,windows")

    def test_parse_chrome_backend_rejects_invalid_value(self) -> None:
        completed = self.run_bash_capture("parse_launch_args --chrome-backend bad-value")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Valid values are: auto, linux, windows", completed.stderr)

    def test_wsl_backend_prefers_windows_when_probes_pass(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            is_wsl2(){ return 0; }
            command_exists(){ [[ "$1" == "powershell.exe" || "$1" == "wslpath" ]]; }
            powershell_is_operational(){ return 0; }
            resolve_wsl_windows_chrome_path(){ printf '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe\\n'; }
            resolve_wsl_launch_backend
            """
        )
        self.assertIn("wsl-windows", resolved)

    def test_wsl_backend_linux_flag_skips_windows_even_when_available(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            WSL_CHROME_BACKEND='linux'
            command_exists(){ [[ "$1" == "powershell.exe" || "$1" == "wslpath" ]]; }
            powershell_is_operational(){ return 0; }
            resolve_wsl_windows_chrome_path(){ printf '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe\\n'; }
            resolve_wsl_launch_backend
            """
        )
        self.assertIn("wsl-linux-fallback", resolved)

    def test_wsl_backend_windows_flag_requires_windows_prerequisites(self) -> None:
        completed = self.run_bash_capture(
            """
            is_wsl(){ return 0; }
            WSL_CHROME_BACKEND='windows'
            command_exists(){ return 1; }
            resolve_wsl_launch_backend
            """
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--chrome-backend windows requires powershell.exe", completed.stderr)

    def test_wsl_backend_windows_flag_selects_windows_when_probes_pass(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            WSL_CHROME_BACKEND='windows'
            command_exists(){ [[ "$1" == "powershell.exe" || "$1" == "wslpath" ]]; }
            powershell_is_operational(){ return 0; }
            resolve_wsl_windows_chrome_path(){ printf '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe\\n'; }
            resolve_wsl_launch_backend
            """
        )
        self.assertIn("wsl-windows", resolved)

    def test_explicit_chrome_backend_is_wsl_only(self) -> None:
        completed = self.run_bash_capture(
            """
            is_wsl(){ return 1; }
            WSL_CHROME_BACKEND='linux'
            ensure_wsl_chrome_backend_scope
            """
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("--chrome-backend is only supported on WSL", completed.stderr)

    def test_wsl_backend_falls_back_to_linux_when_windows_probe_fails(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            is_wsl2(){ return 0; }
            command_exists(){ [[ "$1" == "powershell.exe" || "$1" == "wslpath" ]]; }
            powershell_is_operational(){ POWERSHELL_LAST_ERROR='probe failed'; return 1; }
            resolve_wsl_launch_backend
            """
        )
        self.assertIn("wsl-linux-fallback", resolved)

    def test_ensure_profile_dir_rejects_empty_path_without_invoking_powershell(self) -> None:
        result = self.run_bash(
            """
            is_wsl(){ return 0; }
            calls=0
            command_exists(){ calls=$((calls + 1)); return 0; }
            if ensure_profile_dir ""; then
              status=0
            else
              status=1
            fi
            printf '%s,%s\\n' "${status}" "${calls}"
            """
        )
        self.assertEqual(result, "1,0")

    def test_wsl_linux_fallback_uses_linux_default_profile_dir(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            CHROME_PROFILE_DIR=''
            CHROME_PROFILE_DIR_RAW=''
            ensure_chrome_profile_dir_resolved_for_backend "wsl-linux-fallback"
            printf '%s\\n' "${CHROME_PROFILE_DIR}"
            """
        )
        self.assertEqual(resolved, "/tmp/webvisionkit-chrome-cdp-profile")

    def test_wsl_linux_fallback_host_candidates_are_gateway_first(self) -> None:
        resolved = self.run_bash(
            """
            detect_wsl_gateway_ip(){ printf '172.29.0.1\\n'; }
            resolve_wsl_linux_fallback_host_candidates
            """
        )
        self.assertEqual(resolved, "172.29.0.1\nhost.docker.internal")

    def test_wsl_linux_fallback_auto_falls_back_to_host_docker_internal(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            WSL_CHROME_LAUNCH_BACKEND='wsl-linux-fallback'
            CHROME_HOST_IN_CONTAINER_RAW=''
            CHROME_HOST_IN_CONTAINER='host.docker.internal'
            detect_wsl_gateway_ip(){ printf '172.29.0.1\\n'; }
            probe_chrome_host_from_container(){
              [[ "$1" == "host.docker.internal" ]]
            }
            resolve_wsl_linux_fallback_host_route >/dev/null
            printf '%s\\n' "${CHROME_HOST_IN_CONTAINER}"
            """
        )
        self.assertEqual(resolved, "host.docker.internal")

    def test_wsl_linux_fallback_does_not_probe_when_explicit_chrome_host_set(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            WSL_CHROME_LAUNCH_BACKEND='wsl-linux-fallback'
            CHROME_HOST_IN_CONTAINER_RAW='custom-host'
            CHROME_HOST_IN_CONTAINER='custom-host'
            calls=0
            probe_chrome_host_from_container(){
              calls=$((calls + 1))
              return 1
            }
            resolve_wsl_linux_fallback_host_route >/dev/null
            printf '%s,%s\\n' "${CHROME_HOST_IN_CONTAINER}" "${calls}"
            """
        )
        self.assertEqual(resolved, "custom-host,0")

    def test_wsl_linux_fallback_errors_with_tried_candidates_when_unreachable(self) -> None:
        completed = self.run_bash_capture(
            """
            is_wsl(){ return 0; }
            WSL_CHROME_LAUNCH_BACKEND='wsl-linux-fallback'
            CHROME_HOST_IN_CONTAINER_RAW=''
            CHROME_HOST_IN_CONTAINER='host.docker.internal'
            detect_wsl_gateway_ip(){ printf '172.29.0.1\\n'; }
            probe_chrome_host_from_container(){ return 1; }
            resolve_wsl_linux_fallback_host_route
            """
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("172.29.0.1,host.docker.internal", completed.stderr.replace(" ", ""))

    def test_wsl_windows_discovery_uses_local_appdata_candidate(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            command_exists(){ [[ "$1" == "powershell.exe" || "$1" == "wslpath" ]]; }
            resolve_windows_local_chrome_path_via_powershell(){ printf 'C:\\\\LocalAppData\\\\Google\\\\Chrome\\\\Application\\\\chrome.exe\\n'; }
            is_valid_wsl_windows_chrome_candidate(){
              [[ "$1" == 'C:\\LocalAppData\\Google\\Chrome\\Application\\chrome.exe' ]]
            }
            resolve_wsl_windows_chrome_path
            """
        )
        self.assertEqual(resolved.splitlines()[-1], r"C:\LocalAppData\Google\Chrome\Application\chrome.exe")

    def test_wsl_windows_discovery_prefers_chrome_app_override(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            CHROME_APP='/mnt/c/Custom/chrome.exe'
            is_valid_wsl_windows_chrome_candidate(){ [[ "$1" == '/mnt/c/Custom/chrome.exe' ]]; }
            resolve_wsl_windows_chrome_path
            """
        )
        self.assertEqual(resolved.splitlines()[-1], "/mnt/c/Custom/chrome.exe")

    def test_wsl_windows_discovery_returns_default_program_files_path(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            command_exists(){ return 1; }
            is_valid_wsl_windows_chrome_candidate(){ [[ "$1" == '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe' ]]; }
            resolve_wsl_windows_chrome_path
            """
        )
        self.assertEqual(resolved.splitlines()[-1], "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe")

    def test_wsl_linux_fallback_resets_windows_default_profile_path(self) -> None:
        resolved = self.run_bash(
            """
            CHROME_PROFILE_DIR_RAW=''
            CHROME_PROFILE_DIR='C:\\\\Temp\\\\WebVisionKit\\\\chrome-cdp-profile'
            CHROME_PROFILE_KIND='wsl-windows-default'
            try_resolve_linux_chrome_app(){ printf '/usr/bin/chromium\\n'; }
            ensure_profile_dir(){ return 0; }
            nohup(){ return 0; }
            launch_wsl_linux_fallback >/dev/null
            printf '%s\\n' "${CHROME_PROFILE_DIR}"
            """
        )
        self.assertEqual(resolved, "/tmp/webvisionkit-chrome-cdp-profile")

    def test_launch_macos_includes_start_maximized(self) -> None:
        resolved = self.run_bash(
            """
            resolve_macos_chrome_app(){ printf '/Applications/Google Chrome.app\\n'; }
            ensure_chrome_profile_dir_resolved_for_backend(){ CHROME_PROFILE_DIR='/tmp/wvk-profile'; return 0; }
            ensure_profile_dir(){ return 0; }
            open(){ printf '%s\\n' "$@"; }
            launch_macos
            """
        )
        self.assertIn("--start-maximized", resolved)

    def test_launch_linux_includes_start_maximized(self) -> None:
        resolved = self.run_bash(
            """
            resolve_linux_chrome_app(){ printf '/usr/bin/google-chrome\\n'; }
            ensure_chrome_profile_dir_resolved_for_backend(){ CHROME_PROFILE_DIR='/tmp/wvk-profile'; return 0; }
            ensure_profile_dir(){ return 0; }
            capture_file="$(mktemp)"
            nohup(){ printf '%s\\n' "$@" >"${capture_file}"; }
            launch_linux
            cat "${capture_file}"
            rm -f "${capture_file}"
            """
        )
        self.assertIn("--start-maximized", resolved)

    def test_launch_wsl_windows_includes_start_maximized(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            resolve_wsl_windows_chrome_path(){ printf '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe\\n'; }
            ensure_chrome_profile_dir_resolved_for_backend(){ CHROME_PROFILE_DIR='C:\\\\Temp\\\\WebVisionKit\\\\chrome-cdp-profile'; return 0; }
            to_windows_path(){ printf '%s\\n' "$1"; }
            ensure_profile_dir(){ return 0; }
            capture_file="$(mktemp)"
            powershell.exe(){ printf '%s\\n' "$*" >"${capture_file}"; }
            launch_wsl_windows
            cat "${capture_file}"
            rm -f "${capture_file}"
            """
        )
        self.assertIn("--start-maximized", resolved)

    def test_launch_wsl_linux_fallback_includes_start_maximized(self) -> None:
        resolved = self.run_bash(
            """
            CHROME_PROFILE_DIR_RAW=''
            try_resolve_linux_chrome_app(){ printf '/usr/bin/google-chrome\\n'; }
            ensure_chrome_profile_dir_resolved_for_backend(){ CHROME_PROFILE_DIR='/tmp/wvk-profile'; return 0; }
            ensure_profile_dir(){ return 0; }
            capture_file="$(mktemp)"
            nohup(){ printf '%s\\n' "$@" >"${capture_file}"; }
            launch_wsl_linux_fallback
            cat "${capture_file}"
            rm -f "${capture_file}"
            """
        )
        self.assertIn("--start-maximized", resolved)

    def test_wsl_windows_host_failover_selects_second_candidate(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            WSL_CHROME_LAUNCH_BACKEND='wsl-windows'
            CHROME_HOST_IN_CONTAINER_RAW=''
            CHROME_HOST_IN_CONTAINER='host.docker.internal'
            resolve_wsl_windows_host_candidates(){ printf 'host.docker.internal\\n172.29.0.1\\n'; }
            probe_chrome_host_from_container(){ [[ "$1" == "172.29.0.1" ]]; }
            resolve_wsl_windows_host_route >/dev/null
            printf '%s\\n' "${CHROME_HOST_IN_CONTAINER}"
            """
        )
        self.assertEqual(resolved, "172.29.0.1")

    def test_wsl_windows_host_route_skips_probe_when_explicit_host_set(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            WSL_CHROME_LAUNCH_BACKEND='wsl-windows'
            CHROME_HOST_IN_CONTAINER_RAW='custom-host'
            CHROME_HOST_IN_CONTAINER='custom-host'
            calls=0
            probe_chrome_host_from_container(){ calls=$((calls + 1)); return 1; }
            resolve_wsl_windows_host_route >/dev/null
            printf '%s,%s\\n' "${CHROME_HOST_IN_CONTAINER}" "${calls}"
            """
        )
        self.assertEqual(resolved, "custom-host,0")

    def test_rewrite_ws_url_for_container_rewrites_any_host(self) -> None:
        resolved = self.run_bash(
            """
            CHROME_HOST_IN_CONTAINER='host.docker.internal'
            CHROME_PORT='9222'
            rewrite_ws_url_for_container 'ws://172.29.0.1:9222/devtools/browser/abc'
            """
        )
        self.assertEqual(resolved, "ws://host.docker.internal:9222/devtools/browser/abc")

    def test_rewrite_ws_url_for_container_uses_explicit_container_host(self) -> None:
        resolved = self.run_bash(
            """
            CHROME_HOST_IN_CONTAINER_RAW='custom-host'
            CHROME_HOST_IN_CONTAINER='custom-host'
            CHROME_PORT='9222'
            rewrite_ws_url_for_container 'ws://172.29.0.1:9222/devtools/browser/abc'
            """
        )
        self.assertEqual(resolved, "ws://custom-host:9222/devtools/browser/abc")

    def test_wait_for_chrome_uses_windows_local_powershell_when_http_candidates_fail(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            WSL_CHROME_LAUNCH_BACKEND='wsl-windows'
            CHROME_STARTUP_RETRIES=1
            CHROME_STARTUP_DELAY_SECONDS=0
            CHROME_VERSION_URL='http://127.0.0.1:9222/json/version'
            curl(){ return 1; }
            powershell_is_operational(){ return 0; }
            fetch_windows_local_devtools_version_json_via_powershell(){ printf '{"webSocketDebuggerUrl":"ws://127.0.0.1:9222/devtools/browser/abc"}\\n'; }
            wait_for_chrome >/dev/null
            printf '%s\\n%s\\n' "${HOST_DEVTOOLS_SOURCE_LABEL}" "${HOST_BROWSER_WS_URL_OVERRIDE}"
            """
        )
        self.assertEqual(
            resolved,
            "windows-local-powershell://127.0.0.1:9222/json/version\nws://127.0.0.1:9222/devtools/browser/abc",
        )

    def test_wait_for_chrome_prefers_windows_local_probe_before_http_candidates(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            WSL_CHROME_LAUNCH_BACKEND='wsl-windows'
            CHROME_STARTUP_RETRIES=1
            CHROME_STARTUP_DELAY_SECONDS=0
            calls=0
            curl(){ calls=$((calls + 1)); return 1; }
            powershell_is_operational(){ return 0; }
            fetch_windows_local_devtools_version_json_via_powershell(){ printf '{"webSocketDebuggerUrl":"ws://127.0.0.1:9222/devtools/browser/abc"}\\n'; }
            wait_for_chrome >/dev/null
            printf '%s\\n' "${calls}"
            """
        )
        self.assertEqual(resolved, "0")

    def test_wait_for_chrome_uses_default_http_candidate_without_wsl(self) -> None:
        resolved = self.run_bash(
            """
            CHROME_STARTUP_RETRIES=1
            CHROME_STARTUP_DELAY_SECONDS=0
            CHROME_VERSION_URL='http://127.0.0.1:9222/json/version'
            fetch_devtools_version_json_from_url(){
              if [[ "$1" == "${CHROME_VERSION_URL}" ]]; then
                printf '{"webSocketDebuggerUrl":"ws://127.0.0.1:9222/devtools/browser/http"}\\n'
                return 0
              fi
              return 1
            }
            wait_for_chrome >/dev/null
            printf '%s\\n%s\\n' "${HOST_DEVTOOLS_SOURCE_LABEL}" "${HOST_BROWSER_WS_URL_OVERRIDE}"
            """
        )
        self.assertEqual(
            resolved,
            "http://127.0.0.1:9222/json/version\nws://127.0.0.1:9222/devtools/browser/http",
        )

    def test_cmd_chrome_reuses_existing_devtools_via_windows_local_probe(self) -> None:
        resolved = self.run_bash(
            """
            ensure_browser_launch_prerequisites(){ return 0; }
            fetch_host_devtools_version_json_into_state(){ HOST_DEVTOOLS_SOURCE_LABEL='windows-local-powershell://127.0.0.1:9222/json/version'; HOST_DEVTOOLS_VERSION_JSON='{"webSocketDebuggerUrl":"ws://127.0.0.1:9222/devtools/browser/abc"}'; return 0; }
            launch_wsl(){ echo 'should-not-launch'; return 1; }
            cmd_chrome
            """
        )
        self.assertIn("Reusing existing DevTools endpoint via windows-local-powershell://127.0.0.1:9222/json/version", resolved)
        self.assertTrue(resolved.rstrip().endswith("windows-local-powershell://127.0.0.1:9222/json/version"))

    def test_resolve_browser_ws_url_uses_host_override_before_fetching(self) -> None:
        resolved = self.run_bash(
            """
            HOST_BROWSER_WS_URL_OVERRIDE='ws://127.0.0.1:9222/devtools/browser/abc'
            resolve_browser_ws_url
            """
        )
        self.assertEqual(resolved, "ws://127.0.0.1:9222/devtools/browser/abc")

    def test_cmd_up_preflight_wsl_windows_reports_tried_candidates(self) -> None:
        completed = self.run_bash_capture(
            """
            is_wsl(){ return 0; }
            ensure_hash_tool(){ return 0; }
            ensure_browser_launch_prerequisites(){ return 0; }
            ensure_catalogs(){ return 0; }
            ensure_docker_access(){ return 0; }
            ensure_image(){ return 0; }
            choose_target_selection(){ TARGET_SELECTION_LABEL='input-lab'; SELECTED_TARGET_OVERRIDE=''; SELECTED_EFFECTIVE_TARGET='file:///tmp/input-lab'; return 0; }
            choose_app(){ SELECTED_APP_NAME='interaction_showcase'; return 0; }
            inspect_app(){ APP_DEFAULT_START_TARGET='game://input-lab'; APP_DEFAULT_START_FPS='5.0'; return 0; }
            resolve_effective_target(){ RESOLVED_APP_DEFAULT_TARGET='file:///tmp/input-lab'; return 0; }
            cmd_chrome(){ WSL_CHROME_LAUNCH_BACKEND='wsl-windows'; return 0; }
            wait_for_chrome(){ return 0; }
            CHROME_HOST_IN_CONTAINER_RAW=''
            run_container_devtools_probe(){ WSL_HOST_ROUTE_TRIED='host.docker.internal,172.29.0.1'; return 1; }
            cmd_up
            """
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("host.docker.internal,172.29.0.1", completed.stderr.replace(" ", ""))

    def test_cmd_up_wsl_windows_retries_preflight_after_route_failover(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            ensure_hash_tool(){ return 0; }
            ensure_browser_launch_prerequisites(){ return 0; }
            ensure_catalogs(){ return 0; }
            ensure_docker_access(){ return 0; }
            ensure_image(){ return 0; }
            choose_target_selection(){ TARGET_SELECTION_LABEL='input-lab'; SELECTED_TARGET_OVERRIDE=''; SELECTED_EFFECTIVE_TARGET='file:///tmp/input-lab'; return 0; }
            choose_app(){ SELECTED_APP_NAME='interaction_showcase'; return 0; }
            inspect_app(){ APP_DEFAULT_START_TARGET='game://input-lab'; APP_DEFAULT_START_FPS='5.0'; return 0; }
            resolve_effective_target(){ RESOLVED_APP_DEFAULT_TARGET='file:///tmp/input-lab'; return 0; }
            cmd_chrome(){ WSL_CHROME_LAUNCH_BACKEND='wsl-windows'; return 0; }
            wait_for_chrome(){ return 0; }
            CHROME_HOST_IN_CONTAINER_RAW=''
            run_container_devtools_probe(){
              CHROME_HOST_IN_CONTAINER='172.29.0.1'
              WSL_HOST_ROUTE_MODE='wsl-windows-probed'
              printf 'probe-ok\\n'
              return 0
            }
            cmd_container(){ printf 'container-called\\n'; return 0; }
            cmd_up
            """
        )
        self.assertIn("container-called", resolved)

    def test_cmd_container_applies_wsl_windows_target_normalization(self) -> None:
        completed = self.run_bash_capture(
            """
            is_wsl(){ return 0; }
            WSL_CHROME_LAUNCH_BACKEND='wsl-windows'
            APP_NAME='interaction_showcase'
            APP_DEFAULT_TARGET_URL='file:///home/user/repo/games/input-lab/index.html'
            TARGET_URL_OVERRIDE='file:///home/user/repo/games/input-lab/index.html'
            command_exists(){ [[ "$1" == "wslpath" || "$1" == "curl" || "$1" == "docker" ]]; }
            wslpath(){ printf '\\\\\\\\wsl.localhost\\\\Ubuntu\\\\home\\\\user\\\\repo\\\\games\\\\input-lab\\\\index.html\\n'; }
            ensure_curl_access(){ return 0; }
            ensure_docker_access(){ return 0; }
            resolve_output_layout(){ HOST_OUTPUT_DIR='/tmp'; HOST_SCREENSHOT_DIR='/tmp/screenshots'; SCREENSHOT_SUBPATH='screenshots'; CONTAINER_SAVE_DIR='/data/output/screenshots'; return 0; }
            resolve_container_targets(){ return 0; }
            build_docker_host_args(){ DOCKER_HOST_ARGS=(); return 0; }
            resolve_browser_ws_url(){ printf 'ws://host.docker.internal:9222/devtools/browser/abc\\n'; }
            resolve_ws_url(){ printf '\\n'; }
            docker(){ return 1; }
            cmd_container
            """
        )
        self.assertIn("file://wsl.localhost/Ubuntu/home/user/repo/games/input-lab/index.html", completed.stdout)

    def test_cmd_container_rewrites_browser_websocket_to_container_host(self) -> None:
        completed = self.run_bash_capture(
            """
            APP_NAME='interaction_showcase'
            command_exists(){ [[ "$1" == "curl" || "$1" == "docker" ]]; }
            ensure_curl_access(){ return 0; }
            ensure_docker_access(){ return 0; }
            resolve_output_layout(){ HOST_OUTPUT_DIR='/tmp'; HOST_SCREENSHOT_DIR='/tmp/screenshots'; SCREENSHOT_SUBPATH='screenshots'; CONTAINER_SAVE_DIR='/data/output/screenshots'; return 0; }
            resolve_container_targets(){ return 0; }
            build_docker_host_args(){ CHROME_HOST_IN_CONTAINER='host.docker.internal'; WSL_HOST_ROUTE_MODE='wsl-windows-probed'; DOCKER_HOST_ARGS=(); return 0; }
            resolve_browser_ws_url(){ printf 'ws://172.29.0.1:9222/devtools/browser/abc\\n'; }
            resolve_ws_url(){ printf 'ws://172.29.0.1:9222/devtools/page/xyz\\n'; }
            docker(){ return 1; }
            cmd_container
            """
        )
        self.assertIn("Container browser websocket:  ws://host.docker.internal:9222/devtools/browser/abc", completed.stdout)
        self.assertIn("Container page websocket URL: ws://host.docker.internal:9222/devtools/page/xyz", completed.stdout)

    def test_cmd_doctor_reports_host_side_endpoint_and_container_route(self) -> None:
        resolved = self.run_bash(
            """
            ensure_hash_tool(){ return 0; }
            ensure_curl_access(){ return 0; }
            ensure_docker_access(){ return 0; }
            ensure_browser_launch_prerequisites(){ return 0; }
            detect_hash_tool(){ printf 'sha256sum\\n'; }
            resolve_platform(){ printf 'wsl\\n'; }
            cmd_chrome(){ WSL_CHROME_LAUNCH_BACKEND='wsl-windows'; return 0; }
            wait_for_chrome(){ return 0; }
            curl(){ printf '{"webSocketDebuggerUrl":"ws://172.29.0.1:9222/devtools/browser/abc"}\\n'; return 0; }
            ensure_image(){ return 0; }
            build_docker_host_args(){ CHROME_HOST_IN_CONTAINER='host.docker.internal'; WSL_HOST_ROUTE_MODE='wsl-windows-probed'; DOCKER_HOST_ARGS=(); return 0; }
            run_container_devtools_probe(){ printf 'probe-ok\\n'; return 0; }
            cmd_doctor
            """
        )
        self.assertIn("Host-side DevTools endpoint: http://127.0.0.1:9222/json/version", resolved)
        self.assertIn("Container-side DevTools host: host.docker.internal (wsl-windows-probed)", resolved)

    def test_cmd_doctor_reports_windows_local_powershell_host_endpoint(self) -> None:
        resolved = self.run_bash(
            """
            ensure_hash_tool(){ return 0; }
            ensure_curl_access(){ return 0; }
            ensure_docker_access(){ return 0; }
            ensure_browser_launch_prerequisites(){ return 0; }
            detect_hash_tool(){ printf 'sha256sum\\n'; }
            resolve_platform(){ printf 'wsl\\n'; }
            cmd_chrome(){ WSL_CHROME_LAUNCH_BACKEND='wsl-windows'; return 0; }
            wait_for_chrome(){ HOST_DEVTOOLS_SOURCE_LABEL='windows-local-powershell://127.0.0.1:9222/json/version'; return 0; }
            fetch_host_devtools_version_json_into_state(){ HOST_DEVTOOLS_VERSION_JSON='{"webSocketDebuggerUrl":"ws://127.0.0.1:9222/devtools/browser/abc"}'; return 0; }
            ensure_image(){ return 0; }
            build_docker_host_args(){ CHROME_HOST_IN_CONTAINER='host.docker.internal'; WSL_HOST_ROUTE_MODE='wsl-windows-probed'; DOCKER_HOST_ARGS=(); return 0; }
            run_container_devtools_probe(){ printf 'probe-ok\\n'; return 0; }
            cmd_doctor
            """
        )
        self.assertIn("Host-side DevTools endpoint: windows-local-powershell://127.0.0.1:9222/json/version", resolved)
        self.assertIn("Host browser websocket: ws://127.0.0.1:9222/devtools/browser/abc", resolved)

    def test_normalize_target_url_for_wsl_windows_converts_wsl_file_url(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            WSL_CHROME_LAUNCH_BACKEND='wsl-windows'
            command_exists(){ [[ "$1" == "wslpath" ]]; }
            wslpath(){ printf '\\\\\\\\wsl.localhost\\\\Ubuntu\\\\home\\\\user\\\\repo\\\\games\\\\input-lab\\\\index.html\\n'; }
            normalize_target_url_for_wsl_windows_chrome 'file:///home/user/repo/games/input-lab/index.html'
            """
        )
        self.assertEqual(resolved, "file://wsl.localhost/Ubuntu/home/user/repo/games/input-lab/index.html")

    def test_cmd_up_normalizes_targets_for_wsl_windows_backend(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            ensure_hash_tool(){ return 0; }
            ensure_browser_launch_prerequisites(){ return 0; }
            ensure_catalogs(){ return 0; }
            ensure_docker_access(){ return 0; }
            ensure_image(){ return 0; }
            choose_target_selection(){ TARGET_SELECTION_LABEL='input-lab'; SELECTED_TARGET_OVERRIDE='file:///home/user/repo/games/input-lab/index.html'; SELECTED_EFFECTIVE_TARGET='file:///home/user/repo/games/input-lab/index.html'; return 0; }
            choose_app(){ SELECTED_APP_NAME='interaction_showcase'; return 0; }
            inspect_app(){ APP_DEFAULT_START_TARGET='game://input-lab'; APP_DEFAULT_START_FPS='5.0'; return 0; }
            resolve_effective_target(){ RESOLVED_APP_DEFAULT_TARGET='file:///home/user/repo/games/input-lab/index.html'; return 0; }
            cmd_chrome(){ WSL_CHROME_LAUNCH_BACKEND='wsl-windows'; return 0; }
            wait_for_chrome(){ return 0; }
            run_container_devtools_probe(){ printf 'probe-ok\\n'; return 0; }
            command_exists(){ [[ "$1" == "wslpath" ]]; }
            wslpath(){ printf '\\\\\\\\wsl.localhost\\\\Ubuntu\\\\home\\\\user\\\\repo\\\\games\\\\input-lab\\\\index.html\\n'; }
            cmd_container(){ echo "container-target:${TARGET_URL_OVERRIDE}"; return 0; }
            cmd_up
            """
        )
        self.assertIn("Normalized target override for Windows Chrome: file://wsl.localhost/Ubuntu/home/user/repo/games/input-lab/index.html", resolved)
        self.assertIn("container-target:file://wsl.localhost/Ubuntu/home/user/repo/games/input-lab/index.html", resolved)

    def test_cmd_up_runs_container_preflight_before_container_handoff(self) -> None:
        resolved = self.run_bash(
            """
            ensure_hash_tool(){ return 0; }
            ensure_browser_launch_prerequisites(){ return 0; }
            ensure_catalogs(){ return 0; }
            ensure_docker_access(){ return 0; }
            ensure_image(){ return 0; }
            choose_target_selection(){ TARGET_SELECTION_LABEL='input-lab'; SELECTED_TARGET_OVERRIDE=''; SELECTED_EFFECTIVE_TARGET='file:///tmp/input-lab'; return 0; }
            choose_app(){ SELECTED_APP_NAME='interaction_showcase'; return 0; }
            inspect_app(){ APP_DEFAULT_START_TARGET='game://input-lab'; APP_DEFAULT_START_FPS='5.0'; return 0; }
            resolve_effective_target(){ RESOLVED_APP_DEFAULT_TARGET='file:///tmp/input-lab'; return 0; }
            cmd_chrome(){ return 0; }
            wait_for_chrome(){ return 0; }
            run_container_devtools_probe(){ printf 'probe-ok\\n'; return 0; }
            cmd_container(){ echo 'container-called'; return 0; }
            cmd_up
            """
        )
        self.assertIn("[stage] container_preflight starting", resolved)
        self.assertIn("[stage] container_launch starting", resolved)
        self.assertIn("container-called", resolved)

    def test_cmd_up_preflight_failure_has_targeted_error(self) -> None:
        completed = self.run_bash_capture(
            """
            ensure_hash_tool(){ return 0; }
            ensure_browser_launch_prerequisites(){ return 0; }
            ensure_catalogs(){ return 0; }
            ensure_docker_access(){ return 0; }
            ensure_image(){ return 0; }
            choose_target_selection(){ TARGET_SELECTION_LABEL='input-lab'; SELECTED_TARGET_OVERRIDE=''; SELECTED_EFFECTIVE_TARGET='file:///tmp/input-lab'; return 0; }
            choose_app(){ SELECTED_APP_NAME='interaction_showcase'; return 0; }
            inspect_app(){ APP_DEFAULT_START_TARGET='game://input-lab'; APP_DEFAULT_START_FPS='5.0'; return 0; }
            resolve_effective_target(){ RESOLVED_APP_DEFAULT_TARGET='file:///tmp/input-lab'; return 0; }
            cmd_chrome(){ return 0; }
            wait_for_chrome(){ return 0; }
            run_container_devtools_probe(){ return 1; }
            cmd_up
            """
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Docker is reachable, but the container cannot reach the Chrome DevTools host", completed.stderr)

    def test_cmd_up_container_failure_emits_diagnostics(self) -> None:
        completed = self.run_bash_capture(
            """
            ensure_hash_tool(){ return 0; }
            ensure_browser_launch_prerequisites(){ return 0; }
            ensure_catalogs(){ return 0; }
            ensure_docker_access(){ return 0; }
            ensure_image(){ return 0; }
            choose_target_selection(){ TARGET_SELECTION_LABEL='input-lab'; SELECTED_TARGET_OVERRIDE=''; SELECTED_EFFECTIVE_TARGET='file:///tmp/input-lab'; return 0; }
            choose_app(){ SELECTED_APP_NAME='interaction_showcase'; return 0; }
            inspect_app(){ APP_DEFAULT_START_TARGET='game://input-lab'; APP_DEFAULT_START_FPS='5.0'; return 0; }
            resolve_effective_target(){ RESOLVED_APP_DEFAULT_TARGET='file:///tmp/input-lab'; return 0; }
            cmd_chrome(){ return 0; }
            wait_for_chrome(){ return 0; }
            run_container_devtools_probe(){ printf 'probe-ok\\n'; return 0; }
            CHROME_HOST_IN_CONTAINER='host.docker.internal'
            CHROME_VERSION_URL='http://127.0.0.1:9222/json/version'
            WSL_CHROME_LAUNCH_BACKEND='wsl-windows'
            cmd_container(){ return 2; }
            cmd_up
            """
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("[stage] container_exit code=2", completed.stdout)
        self.assertIn("backend=wsl-windows", completed.stdout)
        self.assertIn("chrome_host_in_container=host.docker.internal", completed.stdout)
        self.assertIn("devtools_endpoint=http://127.0.0.1:9222/json/version", completed.stdout)


if __name__ == "__main__":
    unittest.main()
