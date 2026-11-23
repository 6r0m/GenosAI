"""Codex defaults use the native config writer and preserve unrelated user settings."""
import importlib.util
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import skilltree as ST
sys.path.insert(0, ST.AGENTS)


class CodexSettings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(ST.AGENTS) / "providers/codex/settings.py"
        spec = importlib.util.spec_from_file_location("codex_settings", source)
        cls.settings = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.settings)

    def setUp(self):
        self.policy = {"approval_policy": "never", "sandbox_mode": "danger-full-access"}
        self.user = {"model_reasoning_effort": "high", "windows": {"sandbox": "elevated"}}
        self.layer = {"name": {"type": "user", "file": "/fixture/config.toml"},
                      "version": "original-version", "config": self.user}

    def snapshot(self):
        return {"layers": [self.layer], "config": dict(self.user)}

    def test_native_batch_writes_only_owned_keys_with_version_guard(self):
        server = mock.Mock()
        server.call.side_effect = [self.snapshot(), {"status": "ok"},
                                  {"layers": [{**self.layer, "config": {**self.user, **self.policy}}],
                                   "config": {**self.user, **self.policy}}]
        self.assertTrue(self.settings.configure(server, "/fixture/config.toml", self.policy, True))
        self.assertEqual(server.call.call_args_list[0].args,
                         ("config/read", {"includeLayers": True, "cwd": "/fixture"}))
        method, params = server.call.call_args_list[1].args
        self.assertEqual(method, "config/batchWrite")
        self.assertEqual(params["expectedVersion"], "original-version")
        self.assertFalse(params["reloadUserConfig"])
        self.assertEqual({edit["keyPath"]: edit["value"] for edit in params["edits"]}, self.policy)
        self.assertEqual(len(params["edits"]), 2)

    def test_second_install_and_read_only_check_do_not_write(self):
        self.user.update(self.policy)
        server = mock.Mock()
        server.call.return_value = self.snapshot()
        for apply in (True, False):
            self.assertFalse(self.settings.configure(server, "/fixture/config.toml", self.policy, apply))
        self.assertTrue(all(call.args[0] == "config/read" for call in server.call.call_args_list))

    def test_drift_check_and_conflicting_profile_refuse_before_write(self):
        server = mock.Mock()
        server.call.return_value = self.snapshot()
        with self.assertRaises(RuntimeError):
            self.settings.configure(server, "/fixture/config.toml", self.policy, False)
        self.user["default_permissions"] = ":workspace"
        with self.assertRaises(RuntimeError):
            self.settings.configure(server, "/fixture/config.toml", self.policy, True)
        self.assertTrue(all(call.args[0] == "config/read" for call in server.call.call_args_list))

    def test_public_defaults_cannot_publish_a_model_and_private_fields_are_optional(self):
        tracked = {'approval_policy': 'never', 'sandbox_mode': 'read-only'}
        self.assertEqual(self.settings.compose(tracked, {}), tracked)
        self.assertEqual(self.settings.compose(tracked, {'model': 'fixture-model'}),
                         {**tracked, 'model': 'fixture-model'})
        with self.assertRaises(RuntimeError):
            self.settings.compose({**tracked, 'model': 'published-model'}, {})
        for invalid in ({'unknown': 'x'}, {'model': ''}, {'model': 7}):
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):
                self.settings.compose(tracked, invalid)

    def test_selected_model_updates_only_that_field_and_keeps_native_effort(self):
        policy = {**self.policy, 'model': 'fixture-model'}
        self.user['model'] = 'native-model'
        projected = {**self.user, **policy}
        server = mock.Mock()
        server.call.side_effect = [self.snapshot(), {'status': 'ok'},
                                  {'layers': [{**self.layer, 'config': projected}], 'config': projected}]
        self.assertTrue(self.settings.configure(server, '/fixture/config.toml', policy, True))
        method, params = server.call.call_args_list[1].args
        self.assertEqual(method, 'config/batchWrite')
        self.assertEqual({edit['keyPath']: edit['value'] for edit in params['edits']},
                         {**self.policy, 'model': 'fixture-model'})
        self.assertNotIn('model_reasoning_effort', {edit['keyPath'] for edit in params['edits']})
        self.assertEqual(projected['model_reasoning_effort'], 'high')

    def test_effective_model_override_cannot_report_success(self):
        policy = {**self.policy, 'model': 'fixture-model'}
        self.user.update(policy)
        snapshot = self.snapshot()
        snapshot['config'] = {**self.user, 'model': 'managed-model'}
        server = mock.Mock()
        server.call.return_value = snapshot
        with self.assertRaises(RuntimeError):
            self.settings.configure(server, '/fixture/config.toml', policy, True)
        self.assertEqual(server.call.call_count, 1)

    def test_missing_user_layer_and_overridden_result_are_not_success(self):
        server = mock.Mock()
        server.call.return_value = {"layers": [], "config": {}}
        with self.assertRaises(RuntimeError):
            self.settings.configure(server, "/fixture/config.toml", self.policy, True)
        server.call.side_effect = [self.snapshot(), {"status": "okOverridden"}]
        with self.assertRaises(RuntimeError):
            self.settings.configure(server, "/fixture/config.toml", self.policy, True)

    def test_rpc_errors_and_closed_server_fail_without_exposing_error_payload(self):
        server = self.settings.Server.__new__(self.settings.Server)
        server.process = mock.Mock()
        server.serial = 0
        server.messages = queue.Queue()
        server.messages.put({"method": "unrelated/notification"})
        server.messages.put({"id": 1, "error": {"code": -32600, "message": "synthetic-private-value"}})
        with self.assertRaises(RuntimeError) as raised:
            server.call("config/batchWrite", {})
        self.assertNotIn("synthetic-private-value", str(raised.exception))
        server.messages.put(None)
        with self.assertRaises(RuntimeError):
            server.call("config/read", {})

    def test_main_finishes_the_native_handshake_before_config_reads(self):
        server=mock.Mock()
        def configured(*args):
            server.notify.assert_called_once_with('initialized')
            return False
        with mock.patch.object(self.settings,'Server',return_value=server),mock.patch.object(self.settings,'configure',side_effect=configured),mock.patch.object(sys,'argv',['settings.py','check','/synthetic-owned-home','--codex','fixture']),mock.patch('builtins.print'):
            self.settings.main()
        server.close.assert_called_once()

    def shutdown_server(self):
        server=self.settings.Server.__new__(self.settings.Server)
        server.process=mock.Mock();server.reader=mock.Mock()
        server.process.wait.return_value=0
        server.reader.is_alive.return_value=False
        return server

    def test_shutdown_waits_for_the_native_rpc_drain_before_forcing(self):
        server=self.shutdown_server()
        def wait(timeout):
            if timeout<30:raise subprocess.TimeoutExpired('synthetic-native-drain',timeout)
            return 0
        server.process.wait.side_effect=wait
        server.close()
        server.process.terminate.assert_not_called();server.process.kill.assert_not_called()

    def test_forced_shutdown_does_not_report_clean_completion(self):
        server=self.shutdown_server()
        server.process.wait.side_effect=[subprocess.TimeoutExpired('synthetic',45),0]
        with self.assertRaisesRegex(RuntimeError,'shutdown'):server.close()

    def test_nonzero_native_exit_is_not_a_clean_shutdown(self):
        server=self.shutdown_server();server.process.wait.return_value=7
        with self.assertRaisesRegex(RuntimeError,'shutdown'):server.close()

    def test_live_stdio_reader_does_not_report_clean_shutdown(self):
        server=self.shutdown_server();server.reader.is_alive.return_value=True
        with self.assertRaisesRegex(RuntimeError,'shutdown'):server.close()

    def test_windows_command_shim_uses_native_interpreter_and_selected_home(self):
        with mock.patch.object(self.settings.os, "name", "nt"), \
                mock.patch.object(self.settings.subprocess, "Popen") as popen:
            server = self.settings.Server(r"C:\Tools With Spaces\codex.cmd", ".", r"C:\Selected Home")
            server.reader.join(timeout=1)
        command = popen.call_args.args[0]
        self.assertEqual(command[-4:], ["/d", "/c", r"C:\Tools With Spaces\codex.cmd", "app-server"])
        self.assertEqual(popen.call_args.kwargs["env"]["CODEX_HOME"], r"C:\Selected Home")
        self.assertNotEqual(popen.call_args.kwargs['cwd'],'.','native startup must not pin the selected home')

    @unittest.skipUnless(sys.platform.startswith("linux"), "WSL path translation")
    def test_wsl_command_shim_translates_path_and_propagates_codex_home(self):
        with mock.patch.object(self.settings.subprocess, "check_output", return_value="C:\\Tools With Spaces\\codex.cmd\n"), \
                mock.patch.object(self.settings.subprocess, "Popen") as popen:
            server = self.settings.Server("/mnt/c/Tools With Spaces/codex.cmd", ".", r"C:\Selected Home")
            server.reader.join(timeout=1)
        command = popen.call_args.args[0]
        self.assertEqual(command, ["cmd.exe", "/d", "/c", r"C:\Tools With Spaces\codex.cmd", "app-server"])
        env = popen.call_args.kwargs["env"]
        self.assertEqual(env["CODEX_HOME"], r"C:\Selected Home")
        self.assertIn("CODEX_HOME", env["WSLENV"].split(":"))
        self.assertEqual(popen.call_args.kwargs["cwd"], "/mnt/c")

    @unittest.skipUnless(sys.platform.startswith("linux"), "WSL lifecycle shell")
    def test_windows_discovery_skips_extensionless_npm_launcher(self):
        with tempfile.TemporaryDirectory(dir=Path(ST.REPO) / "tmp") as temporary:
            shim = Path(temporary) / "codex.cmd"
            shim.touch()
            script = r'''
source "$1"
declare -A PROVIDER_DIR=([codex]=.codex)
operation=install
AI_ROOT=fixture
FAILED=0
generic() { :; }
cmd.exe() { printf 'C:\\npm\\codex\r\nC:\\npm\\codex.cmd\r\n'; }
python3() { printf '%s\n' "$@"; }
candidate="$2"
wslpath() { if [[ "$1" == -u && "$2" == *.cmd ]]; then printf '%s\n' "$candidate"; elif [[ "$1" == -u ]]; then printf '/missing/unix-shim\n'; else printf 'C:\\Selected Home\n'; fi; }
codex codex windows "$3"
exit "$FAILED"
'''
            result = subprocess.run(["bash", "-c", script, "fixture",
                                     str(Path(ST.AGENTS) / "providers/codex/lifecycle.sh"),
                                     str(shim), temporary], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(str(shim), result.stdout)


@unittest.skipUnless(shutil.which("codex"), "native Codex required for local config integration")
class NativeCodexSettings(unittest.TestCase):
    def test_native_writer_applies_selected_model_only_and_stays_idempotent(self):
        source = Path(ST.AGENTS) / "providers/codex/settings.py"
        spec = importlib.util.spec_from_file_location("codex_settings_native", source)
        settings = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(settings)
        with tempfile.TemporaryDirectory(dir=Path(ST.REPO) / "tmp") as temporary:
            home = Path(temporary)
            config = home / "config.toml"
            config.write_text('# keep\nmodel = "native-model"\nmodel_reasoning_effort = "low"\n'
                              '[windows]\nsandbox = "elevated"\n')
            policy = {"approval_policy": "never", "sandbox_mode": "read-only", "model": "fixture-model"}

            def apply():
                server = settings.Server(shutil.which("codex"), str(home), str(home))
                server.call("initialize", {"clientInfo": {"name": "agents-sot-test", "version": "1.0"}})
                server.notify("initialized")
                try:
                    return settings.configure(server, str(config), policy, True)
                finally:
                    server.close()

            self.assertTrue(apply())
            projected = config.read_bytes()
            self.assertIn(b'# keep', projected)
            self.assertIn(b'model = "fixture-model"', projected)
            self.assertIn(b'model_reasoning_effort = "low"', projected)
            self.assertIn(b'sandbox = "elevated"', projected)
            self.assertFalse(apply())
            self.assertEqual(config.read_bytes(), projected)

    def test_native_writer_is_idempotent_preserves_config_and_refuses_invalid_toml(self):
        with tempfile.TemporaryDirectory(dir=Path(ST.REPO) / "tmp") as temporary:
            home = Path(temporary)
            config = home / "config.toml"
            original = '# preserve comment\nmodel_reasoning_effort = "high"\n[windows]\nsandbox = "elevated"\n'
            config.write_text(original)
            command = [sys.executable, str(Path(ST.AGENTS) / "providers/codex/settings.py"),
                       "apply", str(home), "--codex", shutil.which("codex")]
            first = subprocess.run(command, capture_output=True, text=True, timeout=60)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            result = config.read_bytes()
            self.assertIn(b'# preserve comment', result)
            self.assertIn(b'model_reasoning_effort = "high"', result)
            self.assertIn(b'sandbox = "elevated"', result)
            second = subprocess.run(command, capture_output=True, text=True, timeout=60)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("already current", second.stdout)
            self.assertEqual(config.read_bytes(), result)
            config.write_text('approval_policy = [invalid TOML\n')
            invalid = config.read_bytes()
            refused = subprocess.run(command, capture_output=True, text=True, timeout=60)
            self.assertNotEqual(refused.returncode, 0)
            self.assertEqual(config.read_bytes(), invalid)

    def test_windows_command_shim_with_spaces_empty_home_and_conflicting_policy(self):
        if os.name == "nt":
            executable = shutil.which("codex")
        elif sys.platform.startswith("linux") and shutil.which("cmd.exe"):
            result = subprocess.run(["cmd.exe", "/d", "/c", "where", "codex.exe"],
                                    capture_output=True, text=True, timeout=15)
            if result.returncode:
                self.skipTest("native Windows Codex executable unavailable")
            executable = result.stdout.splitlines()[0].strip()
        else:
            self.skipTest("native Windows runtime or WSL interop required")
        temporary = tempfile.mkdtemp(dir=Path(ST.REPO) / "tmp")
        try:
            root = Path(temporary)
            shim = root / "Tools With Spaces" / "codex.cmd"
            shim.parent.mkdir()
            shim.write_bytes(('@echo off\r\ncall "' + executable + '" %*\r\n').encode())
            home = root / "Selected Home"
            home.mkdir()
            native_home = str(home) if os.name == "nt" else subprocess.check_output(
                ["wslpath", "-w", str(home)], text=True, timeout=10).strip()
            command = [sys.executable, str(Path(ST.AGENTS) / "providers/codex/settings.py"),
                       "apply", str(home), "--codex", str(shim), "--native-home", native_home]
            first = subprocess.run(command, capture_output=True, text=True, timeout=60)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            config = home / "config.toml"
            projected = config.read_bytes()
            policy=json.loads((Path(ST.AGENTS)/'providers/codex/user-settings.json').read_text())
            import config as local_config
            policy.update(local_config.load()[1].get('codex',{}))
            for name,value in policy.items():
                self.assertIn((name+' = "'+value+'"').encode(),projected)
            second = subprocess.run(command, capture_output=True, text=True, timeout=60)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("already current", second.stdout)
            self.assertEqual(config.read_bytes(), projected)
            config.write_text('default_permissions = ":workspace"\n')
            conflict = config.read_bytes()
            refused = subprocess.run(command, capture_output=True, text=True, timeout=60)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("reconcile it explicitly", refused.stderr)
            self.assertEqual(config.read_bytes(), conflict)
        finally:
            shutil.rmtree(temporary)


if __name__ == "__main__":
    unittest.main()
