"""The Bash rm guard blocks recursive deletes outside scope, and only those.

The guard replaces a `Bash(rm -rf /*)` deny rule that matched every absolute
recursive delete while missing `/bin/rm` entirely - it blocked the honest path
and not the workaround. What matters is therefore behaviour on both sides of
that line, so every case here drives the real hook over its real stdin
contract: the scratch delete that the old rule wrongly blocked must pass, and
the wrapper and absolute-path forms that slipped past it must not.

Deferral (`{}`) means "no decision, normal rules apply", which under
bypassPermissions is an allow. A crash must also defer - the guard fails open
by design, so a bug in it can never wedge a session.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PERMS = os.path.normpath(os.path.join(HERE, os.pardir, "permissions"))
HOOK = os.path.join(PERMS, "guards", "bash_rm_guard.py")
RUNNER = os.path.join(PERMS, "run-guard.sh")
REPO = os.path.realpath(os.path.join(HERE, os.pardir, os.pardir))
HOME = os.path.expanduser("~")
TEMP = tempfile.gettempdir()


# Bare "bash" resolves through Windows PATH, which may hit System32's WSL
# launcher rather than Git Bash; that one cannot see this repo's path at all.
BASH = shutil.which("bash") or "bash"


def sh(path):
    """Spell a path for Git bash, which eats backslashes in an argv string.

    Passing a Windows path straight through turns
    E:\\Workspaces\\...\\run-guard.sh into E:Workspacesrun-guard.sh and the
    script is never found - the same cross-platform spelling problem the guards
    themselves hit, one layer up.
    """
    return path.replace("\\", "/")




def hook_output(command, cwd=REPO, tool="Bash", project_dir=REPO, **fields):
    """Drive the hook; extra keyword fields join the payload (scratchpad_dir)."""
    payload = json.dumps(dict(fields, tool_name=tool, cwd=cwd,
                              tool_input={"command": command}))
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    # Claude Code hands hooks its own environment; the home folder is part of
    # what decides the repo scope, and Windows finds it only via USERPROFILE.
    for name in ("HOME", "USERPROFILE"):
        if name in os.environ:
            env[name] = os.environ[name]
    if project_dir:
        env["CLAUDE_PROJECT_DIR"] = project_dir
    proc = subprocess.run([sys.executable, HOOK], input=payload,
                          capture_output=True, text=True, env=env)
    assert proc.returncode == 0, "guard must always exit 0, got %s" % proc.returncode
    return json.loads(proc.stdout or "{}").get("hookSpecificOutput", {})


def run(command, **kw):
    return hook_output(command, **kw).get("permissionDecision")


def reason(command, **kw):
    return hook_output(command, **kw).get("permissionDecisionReason", "")


def denied(command, **kw):
    return run(command, **kw) == "deny"


class Blocks(unittest.TestCase):
    def test_filesystem_root(self):
        self.assertTrue(denied("rm -rf /"))

    def test_home_via_tilde_is_unresolvable_so_closed(self):
        self.assertTrue(denied("rm -rf ~"))

    def test_unresolvable_variable_target(self):
        self.assertTrue(denied("rm -rf $HOME"))
        self.assertTrue(denied("rm -rf ${SOMEWHERE}/data"))

    def test_system_paths(self):
        for path in ("/etc", "/usr/lib", "/var/lib", "/mnt/c/Windows"):
            with self.subTest(path=path):
                self.assertTrue(denied("rm -rf " + sh(path)))

    def test_repo_root_itself_is_not_a_legal_target(self):
        self.assertTrue(denied("rm -rf " + sh(REPO)))

    def test_temp_ancestor_does_not_allow_removing_the_working_repo_or_git_metadata(self):
        with tempfile.TemporaryDirectory(prefix='guard-root-') as temporary:
            repo=os.path.join(temporary,'project')
            os.makedirs(os.path.join(repo,'.git'))
            for target in (repo,temporary,os.path.join(repo,'.git'),os.path.join(repo,'.git','index')):
                with self.subTest(target=target):
                    self.assertTrue(denied('rm -rf "'+sh(target)+'"',cwd=repo,project_dir=repo))

    def test_repo_parent(self):
        self.assertTrue(denied("rm -rf " + sh(os.path.dirname(REPO))))

    def test_absolute_path_form_the_deny_rule_missed(self):
        # `/bin/rm` never matched `Bash(rm -rf /*)`; basename resolution catches it
        self.assertTrue(denied("/bin/rm -rf /etc"))
        self.assertTrue(denied("/usr/bin/rm -rf /etc"))

    def test_wrappers_are_stripped(self):
        self.assertTrue(denied("timeout 900 rm -rf /etc"))
        self.assertTrue(denied("nohup rm -rf /var/lib"))

    def test_any_offending_subcommand_in_a_compound(self):
        self.assertTrue(denied("ls -la && rm -rf /var/lib"))
        self.assertTrue(denied("echo hi; rm -rf /etc"))

    def test_relative_target_resolves_against_a_preceding_cd(self):
        self.assertTrue(denied("cd /etc && rm -rf conf.d"))

    def test_temp_root_itself_is_not_below_a_temp_dir(self):
        self.assertTrue(denied("rm -rf /tmp"))

    def test_a_glob_directly_under_a_temp_root_is_every_sessions_scratch(self):
        # `/tmp/*` sits below `tmp` only lexically; it names every job's area.
        for target in ("/tmp/*", "/var/tmp/*", "/tmp/*/cache"):
            with self.subTest(target=target):
                self.assertTrue(denied("rm -rf " + target))


class Defers(unittest.TestCase):
    def test_the_scratchpad_delete_the_old_rule_wrongly_blocked(self):
        self.assertIsNone(run(
            "rm -rf /tmp/claude-1000/-mnt-e-repo/sess/scratchpad/ab2", cwd="/tmp"))

    def test_strictly_inside_the_repo(self):
        self.assertIsNone(run("rm -rf %s/tmp/orchestration/run1" % sh(REPO)))

    def test_below_any_temp_named_directory(self):
        for path in ("/tmp/x", "/var/tmp/y",
                     os.path.join(TEMP, "z"),
                     os.path.join(TEMP, "scratch", "build")):
            with self.subTest(path=path):
                self.assertIsNone(run("rm -rf " + sh(path)))

    def test_non_recursive_delete_is_out_of_scope(self):
        self.assertIsNone(run("rm /etc/passwd"))
        self.assertIsNone(run("rm -f /etc/passwd"))

    def test_rmdir_only_removes_empty_dirs(self):
        self.assertIsNone(run("rmdir /etc/foo"))

    def test_commands_without_rm(self):
        self.assertIsNone(run("git status && ls -la /etc"))

    def test_relative_target_under_a_temp_cwd(self):
        self.assertIsNone(run("cd /tmp && rm -rf ab2"))

    def test_a_glob_inside_a_named_temp_child(self):
        self.assertIsNone(run("rm -rf /tmp/job-1/*"))

    def test_a_critical_path_prompt_is_the_permission_hooks_to_answer(self):
        # Claude Code stops for a human on this; rm_scope_allow.py answers.
        self.assertIsNone(run("rm -f /tmp_out_ignore"))

    def test_non_bash_tools_are_not_this_guards_business(self):
        self.assertIsNone(run("rm -rf /etc", tool="Edit"))


class FailsOpen(unittest.TestCase):
    """A guard that cannot parse must never wedge the session."""

    def test_unparseable_quoting_defers(self):
        self.assertIsNone(run('rm -rf "unclosed'))

    def test_malformed_stdin_defers_and_exits_zero(self):
        proc = subprocess.run([sys.executable, HOOK], input="not json",
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout or "{}"), {})

    def test_missing_project_dir_falls_back_to_cwd(self):
        self.assertIsNone(run("rm -rf %s/tmp/x" % sh(REPO), project_dir=None))


class Contract(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='guard-contract-')
        self.addCleanup(self.temporary.cleanup)
        self.repo=self.temporary.name
        os.mkdir(os.path.join(self.repo,'tmp'))
        with open(os.path.join(self.repo,'.gitignore'),'w') as stream:stream.write('/tmp/\n')
        subprocess.run(['git','init','-q',self.repo],check=True,capture_output=True)

    def test_denial_names_the_offending_path_and_the_repo(self):
        payload = json.dumps({"tool_name": "Bash", "cwd": REPO,
                              "tool_input": {"command": "rm -rf /etc"}})
        proc = subprocess.run(
            [sys.executable, HOOK], input=payload, capture_output=True, text=True,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                 "CLAUDE_PROJECT_DIR": REPO})
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PreToolUse")
        self.assertEqual(out["permissionDecision"], "deny")
        # The message names the resolved target; on Windows a POSIX absolute
        # path is drive-prefixed by ntpath.join, so assert the tail, not "/etc".
        self.assertIn("etc", out["permissionDecisionReason"])
        self.assertIn(os.path.basename(REPO), out["permissionDecisionReason"])

    def test_denial_offers_a_way_forward_not_a_question(self):
        # This repo has an ignored tmp/, which comes before the scratchpad.
        scratch = "/tmp/claude-1000/-mnt-e-repo/sess/scratchpad"
        text = reason("rm -rf /etc/probe", cwd=self.repo, project_dir=self.repo, scratchpad_dir=scratch)
        self.assertIn(sh(self.repo) + "/tmp/", text)
        self.assertNotIn(scratch, text)
        for phrase in ("ask the user", "widen the guard"):
            self.assertNotIn(phrase, text)

    def test_without_a_scratchpad_the_denial_names_only_the_repo_tmp(self):
        # Claude Code omits scratchpad_dir when there is none to use.
        text = reason("rm -rf /etc/probe", cwd=self.repo, project_dir=self.repo)
        self.assertIn(sh(self.repo) + "/tmp/", text)
        self.assertNotIn("scratch", text.lower())


class ABroadFolderIsNeverTheRepo(unittest.TestCase):
    """A session started in a home folder or at a drive root has no repo scope.

    Taking that folder as the repo would make everything under it deletable -
    a whole home, or a whole drive - and every "strictly inside the repo" check
    would pass for it.
    """

    HOME = os.path.realpath(os.path.expanduser("~"))

    def test_the_home_folder_and_the_folder_above_it(self):
        target = sh(os.path.join(self.HOME, "Documents", "project"))
        for project in (self.HOME, os.path.dirname(self.HOME)):
            with self.subTest(project=project):
                self.assertTrue(denied("rm -rf " + target, cwd=project,
                                       project_dir=project))

    @unittest.skipIf(os.name == "nt", "WSL drive mounts")
    def test_a_wsl_drive_mount_and_the_windows_profile_under_it(self):
        for project in ("/mnt", "/mnt/e", "/mnt/c/Users", "/mnt/c/Users/sample-user"):
            with self.subTest(project=project):
                self.assertTrue(denied("rm -rf %s/some-project/build" % project,
                                       cwd=project, project_dir=project))

    @unittest.skipUnless(os.name == "nt", "Windows drive roots")
    def test_a_windows_drive_root(self):
        drive = os.path.splitdrive(REPO)[0] + "\\"
        self.assertTrue(denied("rm -rf " + sh(os.path.join(drive, "some-project", "build")),
                               cwd=drive, project_dir=drive))

    def test_temp_areas_are_still_in_scope_from_there(self):
        self.assertIsNone(run("rm -rf /tmp/job-1", cwd=self.HOME, project_dir=self.HOME))

    def test_the_denial_names_no_repo(self):
        # A filesystem or drive root never matched as a repo, but the denial
        # must still say there is none rather than name the root as one.
        root = os.path.splitdrive(REPO)[0] + os.sep
        for project, target in ((self.HOME, os.path.join(self.HOME, "Documents", "project")),
                                (root, os.path.join(root, "srv", "project"))):
            with self.subTest(project=project):
                text = reason("rm -rf " + sh(target), cwd=project, project_dir=project)
                self.assertIn("no working repo", text)
                self.assertNotIn("None", text)


class SymlinkResolution(unittest.TestCase):
    """A temp-named symlink must not launder a target outside the scope.

    Prefix matching on the spelled path let `/tmp/link -> /etc` through: it
    reads as "below a temp directory" while naming something else entirely.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="symlink-probe-")
        self.link = os.path.join(self.dir, "link-to-etc")
        os.symlink("/etc", self.link)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_temp_named_link_to_outside_is_denied(self):
        self.assertTrue(denied("rm -rf " + sh(self.link), cwd="/"))

    def test_path_through_the_link_is_denied(self):
        self.assertTrue(denied("rm -rf " + sh(self.link) + "/passwd", cwd="/"))

    def test_a_real_directory_under_temp_still_defers(self):
        self.assertIsNone(run("rm -rf " + sh(os.path.join(self.dir, "real-sub")),
                              cwd="/"))


class MonitorIsTheSameShellSurface(unittest.TestCase):
    """Monitor runs commands under Bash's permission rules, so it needs the guard.

    The guard gated on `tool_name == "Bash"`, so `Monitor(command="rm -rf ...")`
    reached the shell with no decision at all - a second unguarded path, like
    the PowerShell tool but on every platform.
    """

    def test_monitor_out_of_scope_delete_is_denied(self):
        self.assertTrue(denied("rm -rf /etc/probe", tool="Monitor"))

    def test_monitor_in_scope_delete_still_defers(self):
        self.assertIsNone(run("rm -rf /tmp/probe", tool="Monitor", cwd="/"))

    def test_an_unrelated_tool_is_still_ignored(self):
        self.assertIsNone(run("rm -rf /etc/probe", tool="Read"))


class InterpreterResolution(unittest.TestCase):
    """run-guard.sh must choose a Python that runs, not one that merely exists.

    On Windows `python3` resolves to the Microsoft Store alias: `command -v`
    finds it, executing it prints "Python was not found" and exits 49. The old
    hook command picked it, produced no stdout, and every recursive delete was
    allowed - silently, because the guards fail open. These tests reproduce that
    on any platform by putting an equivalent stub first on PATH.
    """

    def setUp(self):
        self.bin = tempfile.mkdtemp(prefix="stubbin-")
        stub = os.path.join(self.bin, "python3")
        with open(stub, "w") as fh:
            fh.write('#!/bin/sh\n'
                     'echo "Python was not found; run without arguments to '
                     'install from the Microsoft Store" >&2\n'
                     'exit 49\n')
        os.chmod(stub, 0o755)

    def tearDown(self):
        shutil.rmtree(self.bin, ignore_errors=True)

    def _run(self, guard, payload, path=None):
        env = dict(os.environ)
        env["PATH"] = path if path is not None else self.bin + os.pathsep + env["PATH"]
        return subprocess.run([BASH, sh(RUNNER), guard], input=payload,
                              capture_output=True, text=True, env=env)

    def test_a_stub_interpreter_is_skipped_and_the_guard_still_denies(self):
        payload = json.dumps({"tool_name": "Bash", "cwd": "/",
                              "tool_input": {"command": "rm -rf /etc/probe"}})
        proc = self._run("bash_rm_guard.py", payload)
        self.assertIn("bash_rm_guard", proc.stdout,
                      "a non-working python3 must be skipped, not used")

    def test_stdout_is_always_valid_json(self):
        proc = self._run("bash_rm_guard.py", "not json at all")
        json.loads(proc.stdout or "{}")


class NeverWedgesTheSession(unittest.TestCase):
    """A launcher failure must be non-blocking.

    PreToolUse treats exit 2 as a blocking error. These hooks are registered in
    user-level settings, so they run for every session on the machine, in every
    repository - a guard that exits 2 blocks Bash and Edit everywhere until the
    file is restored. That happened once, by renaming the guards directory while
    settings still pointed at it.
    """

    def test_missing_guard_exits_zero_with_no_decision(self):
        proc = subprocess.run([BASH, sh(RUNNER), "no_such_guard.py"],
                              input="", capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout or "{}"), {})

    def test_no_guard_name_exits_zero_with_no_decision(self):
        proc = subprocess.run([BASH, sh(RUNNER)], input="",
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout or "{}"), {})

    def test_failed_or_empty_native_path_mapping_is_non_blocking(self):
        with tempfile.TemporaryDirectory(prefix="native-mapping-") as temporary:
            wrapper = os.path.join(temporary, "probe.sh")
            for mapper in ("return 1", "return 0"):
                with open(wrapper, "w", encoding="utf-8") as stream:
                    stream.write('python3() { printf "nt\\n"; };\n'
                                 'cygpath() { ' + mapper + '; };\n'
                                 'source "$1" bash_rm_guard.py\n')
                proc = subprocess.run([BASH, sh(wrapper), sh(RUNNER)], input="{}",
                                      capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(json.loads(proc.stdout), {})
                self.assertIn("native Python script path", proc.stderr)

    def test_a_missing_launcher_is_non_blocking_unlike_a_missing_guard(self):
        # This is why settings delegate through `bash run-guard.sh` instead of
        # invoking the .py directly: bash reports 127 for an absent script,
        # python reports 2, and only 2 blocks the tool call.
        absent = subprocess.run([BASH, sh(os.path.join(PERMS, "no-such.sh"))],
                                capture_output=True, text=True)
        self.assertNotEqual(absent.returncode, 2)
        direct = subprocess.run([sys.executable, os.path.join(PERMS, "no-such.py")],
                                capture_output=True, text=True)
        self.assertEqual(direct.returncode, 2)


if __name__ == "__main__":
    unittest.main()
