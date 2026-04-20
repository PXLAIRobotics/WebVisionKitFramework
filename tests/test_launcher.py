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

    def test_wsl_backend_prefers_windows_when_probes_pass(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            is_wsl2(){ return 0; }
            command_exists(){ [[ "$1" == "powershell.exe" || "$1" == "wslpath" ]]; }
            powershell_is_operational(){ return 0; }
            powershell_env_passthrough_works(){ return 0; }
            try_resolve_wsl_chrome_app(){ printf '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe\\n'; }
            resolve_wsl_launch_backend
            """
        )
        self.assertEqual(resolved, "wsl-windows")

    def test_wsl_backend_falls_back_to_linux_when_windows_probe_fails(self) -> None:
        resolved = self.run_bash(
            """
            is_wsl(){ return 0; }
            is_wsl2(){ return 0; }
            command_exists(){ [[ "$1" == "powershell.exe" || "$1" == "wslpath" ]]; }
            powershell_is_operational(){ POWERSHELL_LAST_ERROR='probe failed'; return 1; }
            try_resolve_linux_chrome_app(){ printf '/usr/bin/chromium\\n'; }
            resolve_wsl_launch_backend
            """
        )
        self.assertEqual(resolved, "wsl-linux-fallback")

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


if __name__ == "__main__":
    unittest.main()
