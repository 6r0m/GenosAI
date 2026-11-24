"""Windows profile, launcher encoding and selected-home transport boundaries."""
import os
import sys
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / "lifecycle/platform-paths.sh"
BASH = shutil.which("bash")


@unittest.skipUnless(BASH, "requires Bash")
class HostFamily(unittest.TestCase):
    def test_only_native_windows_bash_is_refused(self):
        script = 'uname() { printf "%s\\n" "$FIXTURE_UNAME"; }; source "$1"; host_family'
        for value, expected in (("Linux", "posix"), ("Darwin", "posix"),
                                ("MINGW64_NT-10.0", "windows-bash"),
                                ("MSYS_NT-10.0", "windows-bash"),
                                ("CYGWIN_NT-10.0", "windows-bash")):
            with self.subTest(uname=value):
                result = subprocess.run([BASH, "-c", script, "fixture", HELPER.as_posix()],
                                        env=dict(os.environ, FIXTURE_UNAME=value),
                                        capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)


@unittest.skipUnless(BASH, "requires Bash")
class WindowsProfile(unittest.TestCase):
    def profile(self, value, code="0"):
        env = dict(os.environ, FIXTURE_PROFILE=value, FIXTURE_EXIT=code)
        # Functions avoid falling through to a real PowerShell on noexec checkouts.
        script = ('powershell.exe() { [[ "$*" == *UTF8Encoding* ]] || return 9; printf "%s\\r\\n" "$FIXTURE_PROFILE"; return "$FIXTURE_EXIT"; }; '
                  'timeout() { shift; "$@"; }; source "$1"; windows_profile')
        with tempfile.TemporaryDirectory(prefix="platform-paths-") as temporary:
            probe = Path(temporary) / "probe.sh"
            probe.write_text(script, encoding="utf-8")
            return subprocess.run([BASH, probe.as_posix(), HELPER.as_posix()],
                                  env=env, capture_output=True, text=True, timeout=25)

    def test_profile_with_spaces_is_returned_once_without_carriage_return(self):
        result = self.profile("C:\\Users\\Sample Person")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "C:\\Users\\Sample Person\n")

    def test_unicode_profile_uses_explicit_utf8_output(self):
        result = self.profile("C:\\Users\\Тестовый пользователь")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "C:\\Users\\Тестовый пользователь\n")

    def test_pi_launcher_preserves_unicode_with_utf8_and_crlf(self):
        writer = HELPER.parents[1] / 'providers/pi/lifecycle.sh'
        with tempfile.TemporaryDirectory(prefix='pi-launcher-') as temporary:
            target = Path(temporary) / 'pi-sot.cmd'
            shell = r'C:\Program Files\Git\bin\bash.exe'
            launch = r'C:\Test User\SOT Юникод\launch.sh'
            result = subprocess.run([BASH, '-c',
                                     'source "$1"; pi_write_windows_launcher "$2" "$3" "$4"',
                                     'fixture', writer.as_posix(), target.as_posix(), shell, launch],
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            raw = target.read_bytes()
            self.assertNotIn(b'\n', raw.replace(b'\r\n', b''))
            lines = raw.decode('utf-8').splitlines()
            self.assertEqual(lines[2], 'chcp 65001 >nul || exit /b 1')
            self.assertEqual(lines[3], '"' + shell + '" "' + launch + '" %*')

    def test_pi_package_forwards_owned_windows_environment_without_changing_parent(self):
        writer = HELPER.parents[1] / 'providers/pi/lifecycle.sh'
        original = 'FOREIGN/p:PI_CODING_AGENT_DIR/p:PI_TELEMETRY/u'
        with tempfile.TemporaryDirectory(prefix='pi-native-env-') as temporary:
            capture = Path(temporary) / 'capture.py'
            capture.write_text("import os,sys,json; print(json.dumps({k:os.environ.get(k) for k in ('WSLENV','PI_CODING_AGENT_DIR','PI_TELEMETRY')}))", encoding='utf-8')
            for platform in ('wsl', 'windows'):
                env = dict(os.environ, WSLENV=original)
                script = 'source "$1"; PI_TELEMETRY_VALUE=0; pi_native_package "$2" "$3" "$4" "C:/Synthetic Home/.pi/agent" install "C:/Synthetic Source/agents"; printf "%s\\n" "$WSLENV"'
                result = subprocess.run([BASH, '-c', script, 'fixture', writer.as_posix(),
                                         platform, sys.executable, capture.as_posix()],
                                        env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                lines = result.stdout.splitlines()
                data = json.loads(lines[0])
                self.assertEqual(data['PI_CODING_AGENT_DIR'], 'C:/Synthetic Home/.pi/agent')
                self.assertEqual(data['PI_TELEMETRY'], '0')
                expected = 'FOREIGN/p:PI_CODING_AGENT_DIR:PI_TELEMETRY' if platform == 'windows' else original
                self.assertEqual(data['WSLENV'], expected)
                self.assertEqual(lines[1], original)

    def test_missing_unexpanded_or_failed_result_is_not_a_profile(self):
        for value, code in (("", "0"), ("%USERPROFILE%", "0"), ("C:\\Users\\Sample Person", "7")):
            with self.subTest(code=code, empty=not value):
                result = self.profile(value, code)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
