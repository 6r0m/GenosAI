"""Native profile discovery preserves argument boundaries and refuses unknown results."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / "lifecycle/platform-paths.sh"
BASH = shutil.which("bash")


@unittest.skipUnless(BASH, "requires Bash")
class WindowsProfile(unittest.TestCase):
    def profile(self, value, code="0"):
        env = dict(os.environ, FIXTURE_PROFILE=value, FIXTURE_EXIT=code)
        # Functions avoid falling through to a real cmd.exe on noexec checkouts.
        script = ('cmd.exe() { printf "%s\\r\\n" "$FIXTURE_PROFILE"; return "$FIXTURE_EXIT"; }; '
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

    def test_missing_unexpanded_or_failed_result_is_not_a_profile(self):
        for value, code in (("", "0"), ("%USERPROFILE%", "0"), ("C:\\Users\\Sample Person", "7")):
            with self.subTest(code=code, empty=not value):
                result = self.profile(value, code)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
