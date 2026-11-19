"""File edits stay inside the repo and genuine scratch, and nowhere else.

The guard previously allowed all of `~/.claude`, so an agent could edit
settings.json and the hook registrations - the policy enforcing its own
behaviour. Narrowing that to `.claude/projects` had to happen without breaking
the three things that legitimately live under `.claude`: workflow scripts,
per-project memory, and skills. Skills are the interesting case - they are
symlinks into this repo, so they only stay editable because the guard resolves
symlinks before matching.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.normpath(
    os.path.join(HERE, os.pardir, "permissions", "guards", "repo_guard.py"))
REPO = os.path.realpath(os.path.join(HERE, os.pardir, os.pardir))
HOME = os.path.expanduser("~")
TEMP = tempfile.gettempdir()
BASH = shutil.which("bash") or "bash"


def sh(path):
    """Spell a path for Git bash, which eats backslashes in an argv string.

    Passing a Windows path straight through turns
    E:\\Workspaces\\...\\run-guard.sh into E:Workspacesrun-guard.sh and the
    script is never found - the same cross-platform spelling problem the guards
    themselves hit, one layer up.
    """
    return path.replace("\\", "/")




def decision(file_path, cwd=REPO):
    payload = json.dumps({"tool_name": "Edit", "cwd": cwd,
                          "tool_input": {"file_path": file_path}})
    proc = subprocess.run([sys.executable, GUARD], input=payload,
                          capture_output=True, text=True)
    assert proc.returncode == 0, "guard must always exit 0"
    out = json.loads(proc.stdout or "{}")
    return out.get("hookSpecificOutput", {}).get("permissionDecision")


class Allows(unittest.TestCase):
    def test_inside_the_working_repo(self):
        self.assertIsNone(decision(REPO + "/agents/permissions/guards/repo_guard.py"))

    def test_workflow_scripts_under_claude_projects(self):
        self.assertIsNone(
            decision(os.path.join(HOME, ".claude", "projects", "p", "workflows", "scripts", "w.js")))

    def test_per_project_memory(self):
        self.assertIsNone(
            decision(os.path.join(HOME, ".claude", "projects", "p", "memory", "note.md")))

    def test_temp_areas(self):
        paths = ["/tmp/x/f.txt", os.path.join(TEMP, "z", "f.txt")]
        if os.name != "nt":
            paths.append("/var/tmp/y/f.txt")   # not a location Git Bash mounts
        for path in paths:
            with self.subTest(path=path):
                self.assertIsNone(decision(path))


class DeniesSelfPolicy(unittest.TestCase):
    """`.claude` as a whole is not writable: it holds the agent's own policy."""

    def test_user_settings(self):
        self.assertEqual(decision(os.path.join(HOME, ".claude", "settings.json")), "deny")

    def test_settings_local(self):
        self.assertEqual(
            decision(os.path.join(HOME, ".claude", "settings.local.json")), "deny")

    def test_hook_registrations(self):
        self.assertEqual(decision(os.path.join(HOME, ".claude", "hooks", "x.py")), "deny")

    def test_windows_side_too(self):
        self.assertEqual(
            decision(os.path.join(HOME, ".claude", "settings.json")), "deny")


class DeniesHost(unittest.TestCase):
    def test_system_paths(self):
        for path in ("/etc/passwd", "/usr/lib/x.so", "/mnt/c/Windows/x.dll"):
            with self.subTest(path=path):
                self.assertEqual(decision(path), "deny")


class SymlinkResolution(unittest.TestCase):
    """Links are resolved before matching, in both directions.

    A link out of scope must not be laundered by where it is spelled, and a
    link into the repo - which is how `.claude/skills` reaches this repo - must
    keep working now that `.claude` itself is no longer allowed.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="repo-guard-probe-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_a_temp_named_link_pointing_outside_is_denied(self):
        link = os.path.join(self.dir, "link-to-etc")
        os.symlink("/etc", link)
        self.assertEqual(decision(os.path.join(link, "passwd")), "deny")

    def test_a_link_into_the_repo_is_allowed(self):
        link = os.path.join(self.dir, "link-to-repo")
        os.symlink(REPO + "/agents/skills", link)
        self.assertIsNone(decision(os.path.join(link, "architect/SKILL.md")))


class FailsOpen(unittest.TestCase):
    def test_malformed_stdin(self):
        proc = subprocess.run([sys.executable, GUARD], input="not json",
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout or "{}"), {})

    def test_non_file_tool_is_not_this_guards_business(self):
        payload = json.dumps({"tool_name": "Bash", "cwd": REPO,
                              "tool_input": {"command": "rm -rf /etc"}})
        proc = subprocess.run([sys.executable, GUARD], input=payload,
                              capture_output=True, text=True)
        self.assertEqual(json.loads(proc.stdout or "{}"), {})


class LocalConfiguration(unittest.TestCase):
    """Exercise the installed wrapper in a relocated source, without operator settings."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="guard-config-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.agents = os.path.join(self.tmp, "checkout with spaces", "agents")
        source = os.path.dirname(os.path.dirname(GUARD))
        shutil.copytree(source, os.path.join(self.agents, "permissions"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        helper = os.path.join(os.path.dirname(source), "config.py")
        if os.path.exists(helper):
            shutil.copyfile(helper, os.path.join(self.agents, "config.py"))
        self.config = os.path.join(os.path.dirname(self.agents), "config.local.json")

    def run_guard(self, value=None, target="/opt/session-repo/file.txt", env=None):
        if value is not None:
            with open(self.config, "w", encoding="utf-8") as stream:
                stream.write(value if isinstance(value, str) else json.dumps(value))
        payload = json.dumps({"tool_name": "Edit", "cwd": "/opt/session-repo",
                              "tool_input": {"file_path": target}})
        proc = subprocess.run(
            [BASH, sh(os.path.join(self.agents, "permissions", "run-guard.sh")), "repo_guard.py"],
            input=payload, text=True, capture_output=True, timeout=20, env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        return proc

    def test_clean_home_defaults_allow_project_memory_but_not_policy(self):
        home = "Q:/Users/sample-user" if os.name == "nt" else "/opt/sample-user-home"
        env = dict(os.environ, HOME=home, USERPROFILE=home)
        for suffix, expected in ((".claude/projects/demo/memory/note.md", None),
                                 (".claude/settings.json", "deny"),
                                 ("unrelated/file.txt", "deny")):
            with self.subTest(target=suffix):
                proc = self.run_guard({}, home + "/" + suffix, env)
                self.assertEqual(json.loads(proc.stdout or "{}").get("hookSpecificOutput", {})
                                 .get("permissionDecision"), expected)

    def test_invalid_local_configuration_refuses_even_an_in_repo_edit(self):
        for value in ('{"private_marker":', {"unknown": "private-marker"},
                      {"permissions": {"extra_write_roots": "private-marker"}},
                      {"permissions": {"extra_write_roots": ["relative-root"]}},
                      {"permissions": {"extra_write_roots": ["/"]}},
                      '{"permissions": {}, "permissions": {}}'):
            with self.subTest(case=type(value).__name__):
                proc = self.run_guard(value)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                output = json.loads(proc.stdout or "{}")
                self.assertEqual(output.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")
                self.assertNotIn("private-marker", proc.stdout + proc.stderr)

    def test_unreadable_local_configuration_is_not_absent(self):
        os.mkdir(self.config)
        output = json.loads(self.run_guard().stdout or "{}")
        self.assertEqual(output.get("hookSpecificOutput", {}).get("permissionDecision"), "deny")

    def test_explicit_root_addition_and_its_sibling_are_distinguished(self):
        self.run_guard({"permissions": {"extra_write_roots": ["/opt/additional worktree"]}})
        for target, expected in (("/opt/additional worktree/file.txt", None),
                                 ("/opt/additional worktree-neighbor/file.txt", "deny")):
            payload = json.dumps({"tool_name": "Write", "cwd": "/opt/session-repo",
                                  "tool_input": {"file_path": target}})
            proc = subprocess.run(
                [sys.executable, os.path.join(self.agents, "permissions", "guards", "repo_guard.py")],
                input=payload, text=True, capture_output=True, timeout=20,
            )
            self.assertEqual(json.loads(proc.stdout or "{}").get("hookSpecificOutput", {})
                             .get("permissionDecision"), expected)


class GitBashDrivePaths(unittest.TestCase):
    """Git Bash spells C:\\ as /c/; Windows Python reads that as the current drive.

    A live Windows session refused `rm -rf /c/Users/sample-user/...` while reporting
    the target as `C:\\c\\Users\\sample-user\\...` - an in-scope path denied purely by
    mis-normalisation. It failed closed, which is the safe direction, but /c/...
    and relative paths were not treated equivalently.
    """

    def setUp(self):
        sys.path.insert(0, os.path.join(
            os.path.dirname(GUARD)))
        import _paths
        self.native = _paths.native

    def test_drive_letter_is_read_as_a_drive_on_windows(self):
        if os.name != "nt":
            self.skipTest("behaviour only differs under Windows Python")
        self.assertEqual(self.native("/c/Users/sample-user/x"), "C:/Users/sample-user/x")
        self.assertEqual(self.native("/e/Workspaces/x"), "E:/Workspaces/x")

    def test_paths_with_no_windows_meaning_are_untouched(self):
        # /tmp is deliberately excluded: Git Bash mounts it at the Windows temp
        # directory, so native() maps it. These have no such mapping.
        for path in ("/etc/passwd", "relative/x", "/usr/lib/x"):
            with self.subTest(path=path):
                self.assertEqual(self.native(path), path)

    def test_git_bash_tmp_maps_to_the_windows_temp_dir(self):
        if os.name != "nt":
            self.skipTest("behaviour only differs under Windows Python")
        self.assertEqual(self.native("/tmp/x").lower(), sh(os.path.join(TEMP, "x")).lower())

    def test_no_translation_off_windows(self):
        if os.name == "nt":
            self.skipTest("posix-only assertion")
        self.assertEqual(self.native("/c/Users/sample-user/x"), "/c/Users/sample-user/x")


class PowerShellPosture(unittest.TestCase):
    """The PowerShell tool must be shut off, or it is a second unguarded shell.

    It carries its own `tool_input.command` and the guards match `Bash` only,
    so `Remove-Item -Recurse -Force` would bypass all of them. Disabling it
    beats maintaining a second destructive-command parser for a tool this setup
    reaches through Bash anyway.
    """

    CHECK = os.path.normpath(os.path.join(
        HERE, os.pardir, "permissions", "check-registration.py"))

    def _verdict(self, settings):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(settings, fh)
            path = fh.name
        try:
            proc = subprocess.run([sys.executable, self.CHECK, path],
                                  capture_output=True, text=True)
            return proc.returncode, proc.stdout
        finally:
            os.unlink(path)

    def _base(self):
        return {"env": {"CLAUDE_CODE_USE_POWERSHELL_TOOL": "0"},
                "permissions": {"deny": ["PowerShell"], "allow": ["Monitor"]},
                "hooks": {"PreToolUse": [
                    {"matcher": "Bash|Monitor",
                     "hooks": [{"command": "bash run-guard.sh bash_rm_guard.py"}]},
                    {"matcher": "Edit|Write|NotebookEdit",
                     "hooks": [{"command": "bash run-guard.sh repo_guard.py"}]}],
                    "PermissionRequest": [
                        {"matcher": "Bash|Monitor",
                         "hooks": [{"command": "bash run-guard.sh rm_scope_allow.py"}]}]}}

    def test_correct_posture_passes(self):
        rc, _ = self._verdict(self._base())
        self.assertEqual(rc, 0)

    def test_env_not_disabled_is_rejected(self):
        s = self._base(); s["env"] = {}
        rc, out = self._verdict(s)
        self.assertEqual(rc, 1)
        self.assertIn("CLAUDE_CODE_USE_POWERSHELL_TOOL", out)

    def test_a_narrow_powershell_rule_is_not_a_backstop(self):
        s = self._base()
        s["permissions"]["deny"] = ["PowerShell(Get-ChildItem *)"]
        rc, out = self._verdict(s)
        self.assertEqual(rc, 1)
        self.assertIn("whole-tool", out)

    def test_powershell_star_form_is_accepted(self):
        s = self._base(); s["permissions"]["deny"] = ["PowerShell(*)"]
        rc, _ = self._verdict(s)
        self.assertEqual(rc, 0)

    def test_bash_only_matcher_is_rejected(self):
        s = self._base()
        s["hooks"]["PreToolUse"][0]["matcher"] = "Bash"
        rc, out = self._verdict(s)
        self.assertEqual(rc, 1)
        self.assertIn("Bash|Monitor", out)

    def test_missing_deny_backstop_is_rejected(self):
        s = self._base(); s["permissions"]["deny"] = []
        rc, out = self._verdict(s)
        self.assertEqual(rc, 1)
        self.assertIn("PowerShell deny", out)


class MonitorAllowPosture(unittest.TestCase):
    """Monitor must be allowed as a whole tool, not only guarded.

    The bare `Bash` allow does not approve a Monitor command containing a `$`
    expansion outside bypass and auto mode, so every watch loop in a Manual
    session waits on a prompt. Only a whole-tool rule removes that; a narrow
    `Monitor(...)` rule leaves every other watch command asking.
    """

    CHECK = PowerShellPosture.CHECK
    _verdict = PowerShellPosture._verdict
    _base = PowerShellPosture._base

    def test_whole_tool_allow_passes(self):
        rc, _ = self._verdict(self._base())
        self.assertEqual(rc, 0)

    def test_bash_allow_alone_is_rejected(self):
        s = self._base(); s["permissions"]["allow"] = ["Bash"]
        rc, out = self._verdict(s)
        self.assertEqual(rc, 1)
        self.assertIn("Monitor allow", out)

    def test_a_narrow_monitor_rule_is_rejected(self):
        s = self._base(); s["permissions"]["allow"] = ["Bash", "Monitor(tail *)"]
        rc, out = self._verdict(s)
        self.assertEqual(rc, 1)
        self.assertIn("Monitor allow", out)

    def test_monitor_star_form_is_accepted(self):
        s = self._base(); s["permissions"]["allow"] = ["Monitor(*)"]
        rc, _ = self._verdict(s)
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
