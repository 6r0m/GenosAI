"""Claude settings compose public defaults and private additions into each native file.

Claude Code writes its own user settings too, so the live file has two writers. These tests pin the
contract that makes that safe: only the tracked file's top-level keys are owned, a plan is shown
before anything is written, approval binds to that exact plan, a run that cannot or may not write
leaves every file byte-identical, the plan never prints a value that could be a credential, and the
session-start warning never fails silently or puts anything but a `systemMessage` on stdout.

Fixtures are built from the real tracked file, so the guard posture the preflight insists on is the
production one rather than a stand-in.
"""
import json
import os
import re
import shutil
import shlex
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skilltree as ST

PROVIDER = os.path.join(ST.AGENTS, "providers", "claude")
SETTINGS_PY = os.path.join(PROVIDER, "settings.py")
TRACKED = os.path.join(PROVIDER, "user-settings.json")
ADAPTER = os.path.join(PROVIDER, "session-check.sh")
BASH = shutil.which("bash") or "bash"
POSIX = os.name == "posix"
PLAN_ID = re.compile(r"(?m)^plan id: ([0-9a-f]{12})$")
SECRETS = ("s3cr3t-env-value", "s3cr3t-plugin-value", "s3cr3t-hook-value")


def sh(path):
    """Spell a path for Git Bash, which eats backslashes in an argv string."""
    return path.replace("\\", "/")


def template():
    with open(TRACKED, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def drifted(value):
    """A live file the way Claude Code leaves one: two owned values changed in a session, its own keys
    interleaved with ours."""
    live = {}
    for key, value in value.items():
        live[key] = value
        if key == "model":
            live["theme"] = "dark"
    live["model"] = "sonnet"
    live["autoCompactEnabled"] = False
    live["feedbackDrafts"] = {"draft": "keep me"}
    return live


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.join(ST.REPO, "tmp", "agent-tests", "__claude_settings__")
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.makedirs(self.tmp)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = os.path.join(self.tmp, "repo")
        self.agents = os.path.join(self.root, "ai", "agents")
        shutil.copytree(os.path.join(ST.AGENTS, "permissions"), os.path.join(self.agents, "permissions"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.provider = os.path.join(self.agents, "providers", "claude")
        shutil.copytree(PROVIDER, self.provider, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(os.path.join(ST.AGENTS, "config.py"), os.path.join(self.agents, "config.py"))
        fixture=template()
        fixture.update({'model':'fixture-model','autoCompactEnabled':True,
                        'pluginConfigs':{'langfuse-observability@langfuse-observability':{'options':{}}}})
        write_json(os.path.join(self.provider,'user-settings.json'),fixture)
        self.script = os.path.join(self.provider, "settings.py")
        if POSIX:
            binary = os.path.join(self.tmp, "bin")
            os.makedirs(binary)
            translator = os.path.join(binary, "wslpath")
            with open(translator, "w") as stream:
                stream.write("#!/bin/sh\nprintf 'C:/Fixture%s\\n' \"$2\"\n")
            os.chmod(translator, 0o700)
            self.env_patch = unittest.mock.patch.dict(os.environ, PATH=binary + os.pathsep + os.environ.get("PATH", ""))
            self.env_patch.start()
            self.addCleanup(self.env_patch.stop)

    def tracked(self, side="wsl"):
        with open(os.path.join(self.provider, "user-settings.json")) as stream: value=json.load(stream)
        value={k:v for k,v in value.items() if v is not None}
        root = sh(self.agents)
        if side == "windows" and os.name != "nt":
            root = subprocess.check_output(["wslpath", "-w", self.agents], text=True).strip().replace("\\", "/")
        for groups in value["hooks"].values():
            for group in groups:
                for hook in group["hooks"]:
                    hook["command"] = re.sub(r'"@AGENTS_ROOT@/([^"\n]+)"',
                                             lambda m: shlex.quote(root + "/" + m[1]), hook["command"])
        return value

    def drifted(self):
        return drifted(self.tracked())

    def settings(self, *args, env=None, tracked_path=None):
        argv = [sys.executable, self.script, *args]
        if tracked_path:
            argv += ["--tracked", tracked_path]
        return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              encoding="utf-8", env=env, timeout=60)

    def side(self, name, value):
        folder = os.path.join(self.tmp, name, ".claude")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "settings.json")
        if value is not None:
            write_json(path, value)
        return path

    def plan_id(self, *sides):
        proc = self.settings("check", *self.side_args(*sides))
        match = PLAN_ID.search(proc.stdout)
        self.assertIsNotNone(match, proc.stdout + proc.stderr)
        return match.group(1)

    @staticmethod
    def side_args(*sides):
        out = []
        for name, path in sides:
            out += ["--side", name, path]
        return out

    def backups(self, path):
        folder, base = os.path.split(path)
        return sorted(n for n in os.listdir(folder) if n.startswith(base + ".") and n.endswith(".bak"))


class TrackedFile(Base):
    def test_tracked_file_keeps_the_guard_posture(self):
        checker = os.path.join(ST.AGENTS, "permissions", "check-registration.py")
        proc = subprocess.run([sys.executable, checker, TRACKED], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_preflight_refuses_a_tracked_file_without_the_session_warning(self):
        bad = template()
        bad["hooks"].pop("SessionStart", None)
        path = os.path.join(self.tmp, "tracked.json")
        write_json(path, bad)
        live = self.side("wsl", self.drifted())
        before = read_bytes(live)
        proc = self.settings("check", "--side", "wsl", live, tracked_path=path)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("SessionStart", proc.stdout + proc.stderr)
        self.assertEqual(before, read_bytes(live))

    def test_preflight_refuses_a_hook_that_only_mentions_the_adapter(self):
        bad = template()
        bad["hooks"]["SessionStart"][0]["hooks"][0]["command"] = (
            "echo ai/agents/providers/claude/session-check.sh || echo systemMessage")
        path = os.path.join(self.tmp, "tracked.json")
        write_json(path, bad)
        proc = self.settings("check", "--side", "wsl", self.side("wsl", self.drifted()), tracked_path=path)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("SessionStart", proc.stdout + proc.stderr)

    def test_preflight_refuses_a_second_session_hook_beside_the_warning(self):
        bad = template()
        bad["hooks"]["SessionStart"].append({"hooks": [{"type": "command", "command": "echo hello", "timeout": 5}]})
        path = os.path.join(self.tmp, "tracked.json")
        write_json(path, bad)
        proc = self.settings("check", "--side", "wsl", self.side("wsl", self.drifted()), tracked_path=path)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("exactly one", proc.stdout + proc.stderr)

    def test_preflight_refuses_a_session_hook_without_a_short_timeout(self):
        bad = template()
        bad["hooks"]["SessionStart"][0]["hooks"][0]["timeout"] = 60
        path = os.path.join(self.tmp, "tracked.json")
        write_json(path, bad)
        proc = self.settings("check", "--side", "wsl", self.side("wsl", self.drifted()), tracked_path=path)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("timeout", proc.stdout + proc.stderr)

    def test_preflight_refuses_a_tracked_file_that_drops_a_guard(self):
        bad = template()
        bad["hooks"].pop("PermissionRequest")
        path = os.path.join(self.tmp, "tracked.json")
        write_json(path, bad)
        live = self.side("wsl", self.drifted())
        proc = self.settings("apply", "--side", "wsl", live, "--approve", "0" * 12, tracked_path=path)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("rm_scope_allow.py", proc.stdout + proc.stderr)


class Plan(Base):
    def test_drift_is_planned_with_both_values_and_a_plan_id(self):
        live = self.side("wsl", self.drifted())
        proc = self.settings("check", "--side", "wsl", live)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn('model: "sonnet" → "fixture-model"', proc.stdout)
        self.assertIn("autoCompactEnabled: false → true", proc.stdout)
        self.assertRegex(proc.stdout, PLAN_ID)
        self.assertNotIn("theme", re.sub(r"(?m)^\s*unowned.*$", "", proc.stdout),
                         "an unowned key is information, never a change")

    def test_a_list_change_is_shown_per_element(self):
        live_value = self.tracked()
        live_value["permissions"]["deny"].append("Read(./secrets/**)")
        live = self.side("windows", live_value)
        proc = self.settings("check", "--side", "windows", live)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn('permissions.deny: − "Read(./secrets/**)"', proc.stdout)

    def test_a_side_in_sync_is_clean(self):
        live_value = self.tracked()
        live_value["theme"] = "dark"
        live = self.side("wsl", live_value)
        proc = self.settings("check", "--side", "wsl", live)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_a_missing_target_is_a_failure_with_a_creation_plan(self):
        path = self.side("wsl", None)
        proc = self.settings("check", "--side", "wsl", path)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("will be created", proc.stdout)
        self.assertFalse(os.path.exists(path))

    def test_an_unparsable_target_cannot_be_checked(self):
        path = self.side("wsl", None)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('{"model": "opus",')
        proc = self.settings("check", "--side", "wsl", path)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("wsl: not valid JSON", proc.stdout + proc.stderr)
        self.assertNotRegex(proc.stdout, PLAN_ID)

    def test_the_plan_id_binds_to_the_side_and_its_path(self):
        first = self.side("one", self.drifted())
        second = self.side("two", self.drifted())
        self.assertEqual(read_bytes(first), read_bytes(second))
        self.assertNotEqual(self.plan_id(("wsl", first)), self.plan_id(("wsl", second)))
        self.assertNotEqual(self.plan_id(("wsl", first)), self.plan_id(("windows", first)))


class Redaction(Base):
    def test_the_plan_never_prints_a_value_that_could_be_a_credential(self):
        live_value = self.tracked()
        live_value["env"]["SOME_API"] = SECRETS[0]
        live_value["pluginConfigs"]["langfuse-observability@langfuse-observability"]["options"][
            "LANGFUSE_SECRET_KEY"] = SECRETS[1]
        live_value["hooks"]["Stop"] = [{"hooks": [{"type": "command",
                                                   "command": "notify --pass " + SECRETS[2]}]}]
        live = self.side("wsl", live_value)
        proc = self.settings("check", "--side", "wsl", live)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        for secret in SECRETS:
            self.assertNotIn(secret, proc.stdout + proc.stderr)
        self.assertIn("<redacted #", proc.stdout)
        self.assertIn("env.SOME_API", proc.stdout, "a redacted change still names its key")


class Apply(Base):
    def test_without_a_terminal_or_an_approval_nothing_is_written(self):
        live = self.side("wsl", self.drifted())
        before = read_bytes(live)
        proc = self.settings("apply", "--side", "wsl", live)
        self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
        self.assertIn("--approve", proc.stdout + proc.stderr)
        self.assertEqual(before, read_bytes(live))
        self.assertEqual([], self.backups(live))

    def test_an_approved_plan_merges_owned_keys_and_keeps_claudes_own(self):
        live = self.side("wsl", self.drifted())
        before = read_bytes(live)
        order_before = list(json.loads(before))
        proc = self.settings("apply", "--side", "wsl", live, "--approve", self.plan_id(("wsl", live)))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertRegex(proc.stdout, r"applied 2 changes to wsl; backup \S+\.bak")
        after = json.loads(read_bytes(live))
        for key, value in self.tracked().items():
            self.assertEqual(value, after[key], key)
        self.assertEqual("dark", after["theme"])
        self.assertEqual({"draft": "keep me"}, after["feedbackDrafts"])
        self.assertEqual(order_before, list(after), "key order is Claude Code's, not ours")
        backups = self.backups(live)
        self.assertEqual(1, len(backups))
        self.assertEqual(before, read_bytes(os.path.join(os.path.dirname(live), backups[0])))
        self.assertEqual([], [n for n in os.listdir(os.path.dirname(live)) if n.startswith(".")],
                         "no temporary file is left behind")

    @unittest.skipUnless(POSIX, "file modes are POSIX")
    def test_a_backup_is_never_more_readable_than_owner_only(self):
        root = tempfile.mkdtemp(prefix="claude-settings-")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        live = os.path.join(root, "settings.json")
        value = self.drifted()
        value["env"]["SYNTHETIC_TOKEN"] = SECRETS[0]
        write_json(live, value)
        os.chmod(live, 0o600)
        if stat.S_IMODE(os.stat(live).st_mode) != 0o600:
            self.skipTest("this filesystem does not keep file modes")
        previous = os.umask(0o022)
        try:
            proc = self.settings("apply", "--side", "wsl", live, "--approve", self.plan_id(("wsl", live)))
        finally:
            os.umask(previous)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        [backup] = self.backups(live)
        backup = os.path.join(root, backup)
        self.assertIn(SECRETS[0].encode(), read_bytes(backup), "the copy holds the previous content")
        self.assertEqual(0, stat.S_IMODE(os.stat(backup).st_mode) & 0o077,
                         "a backup of a private settings file must stay private")
        self.assertEqual(0o600, stat.S_IMODE(os.stat(live).st_mode), "the new file keeps the old mode")

    def test_a_second_apply_writes_nothing(self):
        live = self.side("wsl", self.drifted())
        self.settings("apply", "--side", "wsl", live, "--approve", self.plan_id(("wsl", live)))
        before, backups = read_bytes(live), self.backups(live)
        time.sleep(0.01)
        proc = self.settings("apply", "--side", "wsl", live)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("no changes", proc.stdout)
        self.assertEqual(before, read_bytes(live))
        self.assertEqual(backups, self.backups(live))

    def test_a_missing_target_is_created_with_the_owned_keys(self):
        path = self.side("wsl", None)
        proc = self.settings("apply", "--side", "wsl", path, "--approve", self.plan_id(("wsl", path)))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.tracked(), json.loads(read_bytes(path)))

    def test_a_stale_approval_writes_nothing(self):
        live = self.side("wsl", self.drifted())
        approved = self.plan_id(("wsl", live))
        changed = self.drifted()
        changed["feedbackDrafts"] = {"draft": "saved by Claude Code during review"}
        write_json(live, changed)
        before = read_bytes(live)
        proc = self.settings("apply", "--side", "wsl", live, "--approve", approved)
        self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
        self.assertIn("changed since", proc.stdout + proc.stderr)
        self.assertEqual(before, read_bytes(live))
        self.assertEqual([], self.backups(live))

    def test_an_unparsable_second_side_refuses_before_the_first_is_written(self):
        first = self.side("wsl", self.drifted())
        second = self.side("windows", None)
        with open(second, "w", encoding="utf-8") as fh:
            fh.write("[]")
        before = read_bytes(first), read_bytes(second)
        proc = self.settings("apply", "--side", "wsl", first, "--side", "windows", second,
                             "--approve", "0" * 12)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("windows: not a JSON object", proc.stdout + proc.stderr)
        self.assertEqual(before, (read_bytes(first), read_bytes(second)))

    @unittest.skipUnless(POSIX and hasattr(os, "geteuid") and os.geteuid() != 0,
                         "needs POSIX directory permissions and a non-root user")
    def test_a_failed_second_write_is_reported_and_the_first_kept(self):
        root = tempfile.mkdtemp(prefix="claude-settings-")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        first = os.path.join(root, "wsl.json")
        locked = os.path.join(root, "locked")
        os.makedirs(locked)
        second = os.path.join(locked, "settings.json")
        write_json(first, self.drifted())
        write_json(second, self.drifted())
        os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(os.chmod, locked, stat.S_IRWXU)
        try:
            open(os.path.join(locked, "probe"), "w").close()
            self.skipTest("this filesystem ignores directory write permission")
        except OSError:
            pass
        before = read_bytes(second)
        approved = self.plan_id(("wsl", first), ("windows", second))
        proc = self.settings("apply", "--side", "wsl", first, "--side", "windows", second,
                             "--approve", approved)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("applied: wsl; not applied: windows", proc.stdout + proc.stderr)
        self.assertEqual(self.tracked()["model"], json.loads(read_bytes(first))["model"])
        self.assertEqual(before, read_bytes(second))


@unittest.skipUnless(POSIX, "the confirmation prompt is driven through a pseudo-terminal")
class Confirmation(Base):
    def prompt(self, live, answer, between=None):
        import pty
        master, slave = pty.openpty()
        proc = subprocess.Popen([sys.executable, self.script, "apply", "--side", "wsl", live],
                                stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        os.close(slave)
        seen = b""
        while b"Apply these changes? [y/N]" not in seen:
            chunk = proc.stdout.read1(4096) if hasattr(proc.stdout, "read1") else proc.stdout.read(1)
            if not chunk:
                break
            seen += chunk
        if between:
            between()
        os.write(master, answer + b"\n")
        rest, _ = proc.communicate(timeout=60)
        os.close(master)
        return proc.returncode, (seen + rest).decode("utf-8", "replace")

    def test_yes_applies(self):
        live = self.side("wsl", self.drifted())
        code, out = self.prompt(live, b"y")
        self.assertEqual(code, 0, out)
        self.assertEqual("fixture-model", json.loads(read_bytes(live))["model"])

    def test_no_writes_nothing(self):
        live = self.side("wsl", self.drifted())
        before = read_bytes(live)
        code, out = self.prompt(live, b"n")
        self.assertEqual(code, 3, out)
        self.assertEqual(before, read_bytes(live))

    def test_a_save_during_review_aborts_the_write(self):
        live = self.side("wsl", self.drifted())
        saved = self.drifted()
        saved["feedbackDrafts"] = {"draft": "saved by Claude Code during review"}

        def claude_saves():
            write_json(live, saved)
        code, out = self.prompt(live, b"y", between=claude_saves)
        self.assertEqual(code, 3, out)
        self.assertIn("changed since", out)
        self.assertEqual(saved, json.loads(read_bytes(live)))


class HookMode(Base):
    def env(self, home):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
        env["HOME"] = env["USERPROFILE"] = home
        return env

    def home(self, value):
        path = self.side("home", value)
        return os.path.dirname(os.path.dirname(path))

    def test_a_clean_side_answers_with_the_marker(self):
        proc = self.settings("hook", env=self.env(self.home(self.tracked())))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual("clean", proc.stdout.strip())

    def test_drift_names_keys_never_values(self):
        live = self.drifted()
        live["env"]["SOME_API"] = SECRETS[0]
        proc = self.settings("hook", env=self.env(self.home(live)))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        message = json.loads(proc.stdout)["systemMessage"]
        self.assertIn("model", message)
        self.assertIn("env", message)
        self.assertNotIn("sonnet", message)
        self.assertNotIn(SECRETS[0], proc.stdout)

    def test_an_unreadable_tracked_file_is_reported_not_hidden(self):
        bad = os.path.join(self.tmp, "tracked.json")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("{")
        proc = self.settings("hook", env=self.env(self.home(self.tracked())), tracked_path=bad)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("could not run", json.loads(proc.stdout)["systemMessage"])


class Sandbox(Base):
    """A copy of permissions/ and this provider, and a home whose settings match the tracked file."""

    def setUp(self):
        super().setUp()
        self.homedir = os.path.join(self.tmp, "home")
        os.makedirs(os.path.join(self.homedir, ".claude"))
        self.live = os.path.join(self.homedir, ".claude", "settings.json")
        write_json(self.live, self.tracked())

    def command(self):
        """The registered SessionStart command, pointed at the sandbox copy instead of the checkout."""
        entries = self.tracked()["hooks"]["SessionStart"]
        command = next(h["command"] for e in entries for h in e["hooks"] if "session-check.sh" in h["command"])
        return command


class SessionWarning(Sandbox):
    """The registered hook command, its adapter, and run-guard.sh, exactly as Claude Code runs them."""

    def run_hook(self, command=None, path=None):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
        env["HOME"] = env["USERPROFILE"] = self.homedir
        if path is not None:
            env["PATH"] = path
        return subprocess.run([BASH, "-c", command or self.command()], input="{}", capture_output=True,
                              text=True, env=env, timeout=60)

    def adapter(self, path=None):
        return self.run_hook(command='bash "%s"' % sh(os.path.join(self.provider, "session-check.sh")),
                             path=path)

    def warning(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)["systemMessage"]

    def test_a_clean_side_prints_nothing(self):
        proc = self.run_hook()
        self.assertEqual((0, ""), (proc.returncode, proc.stdout), proc.stderr)

    def test_drift_prints_only_the_system_message(self):
        live = self.drifted()
        write_json(self.live, live)
        self.assertIn("model", self.warning(self.run_hook()))

    def test_a_missing_script_warns(self):
        os.unlink(os.path.join(self.provider, "settings.py"))
        self.assertNotEqual(0, self.adapter().returncode)
        self.assertIn("could not run", self.warning(self.run_hook()))

    def test_a_crashing_script_warns(self):
        with open(os.path.join(self.provider, "settings.py"), "w", encoding="utf-8") as fh:
            fh.write("raise SystemExit(1)\n")
        self.assertIn("could not run", self.warning(self.run_hook()))

    def test_run_guards_no_decision_fallback_warns(self):
        with open(os.path.join(self.provider, "settings.py"), "w", encoding="utf-8") as fh:
            fh.write("print('{}')\n")
        self.assertIn("could not run", self.warning(self.run_hook()))

    @unittest.skipUnless(POSIX, "builds a PATH of stub interpreters")
    def test_no_runnable_python_warns(self):
        stubs = os.path.join(self.tmp, "stubbin")
        os.makedirs(stubs)
        for name in ("python3", "python", "py", "python3.exe", "python.exe"):
            with open(os.path.join(stubs, name), "w") as fh:
                fh.write("#!/bin/sh\necho 'Python was not found' >&2\nexit 49\n")
            os.chmod(os.path.join(stubs, name), 0o755)
        for tool in ("bash", "dirname", "cat"):
            os.symlink(shutil.which(tool), os.path.join(stubs, tool))
        self.assertIn("could not run", self.warning(self.run_hook(path=stubs)))

    def test_a_missing_adapter_still_warns(self):
        os.unlink(os.path.join(self.provider, "session-check.sh"))
        self.assertIn("could not run", self.warning(self.run_hook()))


class RegisteredHook(Sandbox):
    """selfcheck.sh's judgement of the hook a live file registers: clean only on exit 0, no output, in time."""

    def register(self, command, timeout=5):
        """Register a live command; its runtime result is what the checker judges."""
        value = self.tracked()
        value["hooks"]["SessionStart"] = [{"hooks": [{"type": "command", "command": command,
                                                      "timeout": timeout}]}]
        write_json(self.live, value)

    def judge(self):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
        env["HOME"] = env["USERPROFILE"] = self.homedir
        return subprocess.run([sys.executable, SETTINGS_PY, "registered-hook", "--settings", self.live],
                              capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)

    def test_the_registered_warning_on_a_clean_side_is_clean(self):
        self.register(self.command())
        proc = self.judge()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_a_silent_nonzero_exit_is_not_clean(self):
        self.register("true session-check.sh; exit 42")
        proc = self.judge()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("exit 42", proc.stdout)

    def test_any_output_is_not_clean(self):
        self.register("printf 'hello' # session-check.sh")
        self.assertEqual(self.judge().returncode, 1)

    def test_a_run_slower_than_its_timeout_is_not_clean(self):
        self.register("sleep 2 # session-check.sh", timeout=1)
        proc = self.judge()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("timeout", proc.stdout)

    def test_no_registered_warning_cannot_be_judged(self):
        value = self.tracked()
        value["hooks"].pop("SessionStart")
        write_json(self.live, value)
        proc = self.judge()
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("not registered", proc.stdout)


class PortableHooks(Sandbox):
    def test_applied_hooks_execute_the_relocated_owner_with_shell_metacharacters(self):
        relocated = os.path.join(self.tmp, "checkout space ' ü $(echo injected)")
        os.rename(self.root, relocated)
        provider = os.path.join(relocated, "ai", "agents", "providers", "claude")
        script = os.path.join(provider, "settings.py")
        command = [sys.executable, script, "check", "--side", "wsl", self.live]
        plan = subprocess.run(command, capture_output=True, text=True, timeout=30)
        pid = PLAN_ID.search(plan.stdout)
        self.assertIsNotNone(pid, plan.stdout + plan.stderr)
        command[2] = "apply"
        applied = subprocess.run([*command, "--approve", pid.group(1)], capture_output=True,
                                 text=True, timeout=30)
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        guard = os.path.join(relocated, "ai", "agents", "permissions", "guards", "repo_guard.py")
        with open(guard, "w", encoding="utf-8") as stream:
            stream.write('print(\'{"probe_owner": "relocated"}\')\n')
        value = json.loads(read_bytes(self.live))
        hook = next(h["command"] for group in value["hooks"]["PreToolUse"]
                    for h in group["hooks"] if "repo_guard.py" in h["command"])
        proc = subprocess.run([BASH, "-c", hook], input="{}", capture_output=True,
                              text=True, encoding="utf-8", timeout=20,
                              env=dict(os.environ, MSYS2_ARG_CONV_EXCL="*", MSYS_NO_PATHCONV="1"))
        self.assertEqual(json.loads(proc.stdout or "{}").get("probe_owner"), "relocated", proc.stderr)


class LocalSettings(Base):
    def local(self, value):
        path = os.path.join(os.path.dirname(self.agents), "config.local.json")
        write_json(path, value)
        return path

    def test_sparse_override_adds_rules_and_preserves_required_defaults(self):
        local = self.local({"claude": {"model": "sonnet", "permissions": {
            "allow": ["Read(./public-fixture/**)"], "deny": ["Edit(./protected-fixture/**)"]}}})
        local_before = read_bytes(local)
        live = self.side("wsl", self.drifted())
        result = self.settings("apply", "--side", "wsl", live,
                               "--approve", self.plan_id(("wsl", live)))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        value = json.loads(read_bytes(live))
        self.assertEqual(value["model"], "sonnet")
        for kind in ("allow", "deny"):
            self.assertTrue(set(template()["permissions"][kind]) <= set(value["permissions"][kind]))
        self.assertIn("Read(./public-fixture/**)", value["permissions"]["allow"])
        self.assertIn("Edit(./protected-fixture/**)", value["permissions"]["deny"])
        self.assertEqual(read_bytes(local), local_before)

    def test_changed_local_input_invalidates_approval_without_writes(self):
        self.local({"permissions": {"extra_write_roots": ["/opt/first-worktree"]}})
        live = self.side("wsl", self.drifted())
        approved = self.plan_id(("wsl", live))
        before = read_bytes(live)
        self.local({"permissions": {"extra_write_roots": ["/opt/second-worktree"]}})
        result = self.settings("apply", "--side", "wsl", live, "--approve", approved)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertEqual(read_bytes(live), before)
        self.assertEqual(self.backups(live), [])

    def test_jsonc_comments_and_parser_changes_bind_the_approved_plan(self):
        vendor=os.path.join(self.agents,'vendor')
        shutil.copytree(os.path.join(ST.AGENTS,'vendor'),vendor,ignore=shutil.ignore_patterns('__pycache__'))
        local=os.path.join(os.path.dirname(self.agents),'config.local.jsonc')
        with open(local,'w') as stream:stream.write('{/* preferences */"claude":{"model":"sonnet"}}')
        live=self.side('wsl',self.drifted())
        approved=self.plan_id(('wsl',live));before=read_bytes(live)
        parser=os.path.join(vendor,'jsonc','_util.py')
        with open(parser,'a') as stream:stream.write('\n# Synthetic parser revision\n')
        result=self.settings('apply','--side','wsl',live,'--approve',approved)
        self.assertEqual(result.returncode,3,result.stdout+result.stderr)
        self.assertEqual(read_bytes(live),before);self.assertEqual(self.backups(live),[])
        result=self.settings('apply','--side','wsl',live,'--approve',self.plan_id(('wsl',live)))
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(read_bytes(live))['model'],'sonnet')

    def test_invalid_or_guard_weakening_local_input_writes_nothing(self):
        live = self.side("wsl", self.drifted())
        before = read_bytes(live)
        for value in ({"unknown": "private-marker"}, {"claude": {"hooks": {}}},
                      {"permissions": {"extra_write_roots": ["/"]}},
                      {"claude": {"model": 2}},
                      {"claude": {"env": {"CLAUDE_CODE_USE_POWERSHELL_TOOL": "1"}}}):
            with self.subTest(case=value.keys()):
                self.local(value)
                result = self.settings("apply", "--side", "wsl", live, "--approve", "0" * 12)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn("private-marker", result.stdout + result.stderr)
                self.assertEqual(read_bytes(live), before)
                self.assertEqual(self.backups(live), [])


if __name__ == "__main__":
    unittest.main()
