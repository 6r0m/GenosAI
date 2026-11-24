"""The installer's WSL half preserves resource wiring and native provider settings.

Codex scans its skill routes recursively. A whole-directory link to the SOT therefore hands Codex
Claude Code's synced/ cache as extra skills, and a per-skill route needs its own .shared for a skill's
`../.shared/` reference to resolve lexically. These tests run the real install.sh and uninstall.sh
from a copy of ai/agents/ into a sandbox home, with a planted non-skill tree standing in for the cache.
The real cache is untracked, so without the planted tree the leak assertion would pass on any checkout
that simply lacks it.

The Windows half is out of reach here by design: install.sh takes the Windows profile from PowerShell,
not from HOME, so every run gets an explicit environment whose PATH resolves no Windows executable, and
the tests skip rather than run when one would resolve.
"""
import os
import json
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skilltree as ST

SAFE_PATH = ST.POSIX_TEST_PATH
WINDOWS_REACHABLE = any(shutil.which(exe, path=SAFE_PATH) for exe in ("cmd.exe", "powershell.exe"))


def _snapshot(root):
    """Relative path -> size for every file under root, links not followed."""
    found = {}
    for base, dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(base, name)
            found[os.path.relpath(path, root)] = os.lstat(path).st_size
    return found


def _route(home):
    """name -> link target (realpath) or None for a real entry, for ~/.codex/skills."""
    route = os.path.join(home, ".codex", "skills")
    return {
        name: os.path.realpath(os.path.join(route, name)) if os.path.islink(os.path.join(route, name)) else None
        for name in os.listdir(route)
    }


@unittest.skipUnless(sys.platform.startswith("linux"), "install.sh's WSL half runs under Linux only")
@unittest.skipIf(WINDOWS_REACHABLE, "a Windows executable resolves on the restricted PATH")
class InstallerWiring(unittest.TestCase):
    def setUp(self):
        # Under the gitignored repo tmp/, like the other fixture trees here. Every link the
        # scripts create points inside this tree, so removing it never reaches the real SOT.
        self.tmp = os.path.join(ST.REPO, "tmp", "agent-tests", "__install_tree__")
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.makedirs(self.tmp)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        # The copy: what install.sh needs, with the untracked cache left out and a stand-in planted.
        self.copy = os.path.join(self.tmp, "repo", "ai", "agents")
        os.makedirs(self.copy)
        for name in ("AGENTS.md", "agent-ignore", "config.py", "package.json"):
            shutil.copy2(os.path.join(ST.AGENTS, name), self.copy)
        secret_dir = os.path.join(self.tmp, 'repo/secrets')
        os.makedirs(secret_dir)
        with open(os.path.join(secret_dir, 'primary.key'), 'w') as stream:
            stream.write('synthetic-key')
        # permissions/ too: the Claude settings preflight reuses its guard-posture checker.
        for directory in ("scripts", "lifecycle", "providers", "permissions"):
            shutil.copytree(os.path.join(ST.AGENTS, directory), os.path.join(self.copy, directory), ignore=shutil.ignore_patterns("__pycache__"))
        with open(os.path.join(ST.AGENTS, 'tests/providers/pi/profiles.json')) as stream:
            profiles=json.load(stream)
        with open(os.path.join(self.copy, 'providers/pi/runtime/profiles.json'), 'w') as stream:
            json.dump(profiles,stream)
        with open(os.path.join(os.path.dirname(self.copy),'config.local.json'),'w') as stream:
            json.dump({'pi':{'secret_root':secret_dir,'ownership_root':os.path.dirname(secret_dir)},
                       'codex':{'approval_policy':'never','sandbox_mode':'danger-full-access',
                                'model':'fixture-model'}},stream)
        self.skills = os.path.join(self.copy, "skills")
        shutil.copytree(ST.SKILLS, self.skills, ignore=shutil.ignore_patterns("synced", "__pycache__"))
        leaked = os.path.join(self.skills, "synced", "bucket", "leaked-skill")
        os.makedirs(leaked)
        with open(os.path.join(leaked, "SKILL.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nname: leaked-skill\ndescription: stands in for the claude.ai cache.\n---\n")
        self.real_skills = sorted(
            n for n in os.listdir(self.skills) if os.path.isfile(os.path.join(self.skills, n, "SKILL.md"))
        )

        # The sandbox home: Codex's own entries that the installer must never touch.
        self.home = os.path.join(self.tmp, "home")
        codex = os.path.join(self.home, ".codex", "skills")
        for own in (".system", "local-skill"):
            os.makedirs(os.path.join(codex, own))
            with open(os.path.join(codex, own, "SKILL.md"), "w", encoding="utf-8") as fh:
                fh.write(own + "\n")
        os.makedirs(os.path.join(self.home, ".agents"))

        # Claude's user settings already in sync with the tracked file, as on a machine that installed
        # before; a home that differs needs an approved plan (ClaudeSettingsLifecycle below).
        self.tracked = os.path.join(self.copy, "providers", "claude", "user-settings.json")
        with open(self.tracked, encoding="utf-8") as stream: tracked=json.load(stream)
        tracked['model']='fixture-model'
        with open(self.tracked,'w',encoding="utf-8") as stream: json.dump(tracked,stream)
        self.settings = os.path.join(self.home, ".claude", "settings.json")
        os.makedirs(os.path.dirname(self.settings))
        owner = [sys.executable, os.path.join(self.copy, "providers", "claude", "settings.py")]
        side = ["--side", "wsl", self.settings]
        plan = subprocess.run([*owner, "check", *side], capture_output=True, text=True, timeout=30)
        pid = re.search(r"(?m)^plan id: ([0-9a-f]{12})$", plan.stdout)
        self.assertIsNotNone(pid, plan.stdout + plan.stderr)
        applied = subprocess.run([*owner, "apply", *side, "--approve", pid.group(1)],
                                 capture_output=True, text=True, timeout=30)
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)

    def run_script(self, name, *args, extra_env=None):
        env = {"HOME": self.home, "PATH": SAFE_PATH, "TMPDIR": self.tmp}
        env.update(extra_env or {})
        if '--platform' not in args: args=(*args,'--platform','both')
        if '--provider' not in args: args=(*args,'--provider','all')
        proc = subprocess.run(
            ["bash", os.path.join(self.copy, "scripts", name), *args],
            env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120,
        )
        # The isolated Windows side makes either operation partial despite completed WSL work.
        self.assertIn("Windows side skipped", proc.stderr, "the Windows half was not isolated")
        self.assertNotEqual(proc.returncode, 0, 'a partial dual-platform operation must fail')
        self.assertNotIn('Done:', proc.stdout)
        return proc

    def errors(self, proc):
        return [l for l in (proc.stdout + proc.stderr).splitlines() if l.startswith("error")]

    def test_native_windows_bash_refuses_before_any_change(self):
        if type(self) is not InstallerWiring:
            self.skipTest('host refusal is platform-generic')
        shim = os.path.join(self.tmp, "fake-uname.sh")
        with open(shim, "w", encoding="utf-8") as fh:
            fh.write('uname() { printf "MINGW64_NT-10.0\\n"; }\n')
        before = _snapshot(self.home)
        proc = subprocess.run(
            ["bash", os.path.join(self.copy, "scripts", "install.sh"),
             "--provider", "codex", "--platform", "both"],
            env={"HOME": self.home, "PATH": SAFE_PATH, "TMPDIR": self.tmp, "BASH_ENV": shim},
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("not native Windows Bash", proc.stderr)
        self.assertEqual(before, _snapshot(self.home), "a refused host must not change the home")

    def test_codex_route_links_only_real_skills_and_shared(self):
        os.symlink(self.skills, os.path.join(self.home, ".agents", "skills"))
        before = _snapshot(self.copy)

        first = self.run_script("install.sh")
        self.assertEqual([], self.errors(first))
        for name in (".claude/CLAUDE.md", ".codex/AGENTS.md", ".agents/AGENTS.md"):
            with self.subTest(global_link=name):
                path = os.path.join(self.home, name)
                self.assertTrue(os.path.islink(path))
                self.assertEqual(os.path.realpath(os.path.join(self.copy, "AGENTS.md")),
                                 os.path.realpath(path))
        self.assertFalse(
            os.path.lexists(os.path.join(self.home, ".agents", "skills")),
            "a whole-directory ~/.agents/skills link lets Codex scan the SOT, synced/ included",
        )
        self.assertEqual(before, _snapshot(self.copy), "retiring the link changed what it pointed at")

        route = _route(self.home)
        expected = {n: os.path.realpath(os.path.join(self.skills, n)) for n in self.real_skills}
        expected[".shared"] = os.path.realpath(os.path.join(self.skills, ".shared"))
        self.assertEqual(expected, {n: t for n, t in route.items() if t is not None})
        self.assertNotIn("synced", route)
        self.assertEqual({".system": None, "local-skill": None},
                         {n: t for n, t in route.items() if t is None})
        for own in (".system", "local-skill"):
            with open(os.path.join(self.home, ".codex", "skills", own, "SKILL.md"), encoding="utf-8") as fh:
                self.assertEqual(own + "\n", fh.read())
        shared = os.path.normpath(
            os.path.join(self.home, ".codex", "skills", "architect", "..", ".shared", "review-contract.md"))
        self.assertTrue(os.path.isfile(shared), "../.shared does not resolve lexically from a skill link")
        self.assertEqual(os.path.realpath(self.skills),
                         os.path.realpath(os.path.join(self.home, ".claude", "skills")))

        second = self.run_script("install.sh")
        self.assertEqual([], self.errors(second))
        wiring = [l for l in second.stdout.splitlines() if re.search(r"\.(codex|agents)/skills", l)]
        self.assertTrue(wiring and all(l.startswith("ok") for l in wiring), "second run changed the wiring")
        self.assertEqual(route, _route(self.home))

        self.run_script("uninstall.sh")
        self.assertEqual({".system": None, "local-skill": None}, _route(self.home))
        self.assertFalse(os.path.lexists(os.path.join(self.home, ".claude", "skills")))

    def test_a_real_agents_skills_directory_is_not_ours(self):
        own = os.path.join(self.home, ".agents", "skills")
        os.makedirs(own)
        sentinel = os.path.join(own, "sentinel.txt")
        with open(sentinel, "w", encoding="utf-8") as fh:
            fh.write("keep me\n")

        proc = self.run_script("install.sh")

        self.assertTrue(os.path.isdir(own) and not os.path.islink(own))
        self.assertEqual(["sentinel.txt"], os.listdir(own))
        with open(sentinel, encoding="utf-8") as fh:
            self.assertEqual("keep me\n", fh.read())
        self.assertRegex(proc.stdout, r"(?m)^kept\s+\S*/\.agents/skills \(not an SOT link",
                         "the installer did not report the directory as not ours")

    @unittest.skipUnless(shutil.which('codex'), 'native Codex required for selected lifecycle check')
    def test_selected_codex_install_applies_defaults_and_is_idempotent(self):
        if type(self) is not InstallerWiring:
            self.skipTest('selected Codex lifecycle is exercised by the wiring fixture')
        binaries = os.path.join(self.tmp, 'bin')
        os.makedirs(binaries)
        os.symlink(shutil.which('codex'), os.path.join(binaries, 'codex'))
        config = os.path.join(self.home, '.codex/config.toml')
        original = '# preserve comment\nmodel_reasoning_effort = "high"\n'
        with open(config, 'w') as stream:
            stream.write(original)
        env = {'PATH': binaries + ':' + SAFE_PATH}
        first = self.run_script('install.sh', '--provider', 'codex', extra_env=env)
        self.assertEqual([], self.errors(first), first.stdout + first.stderr)
        self.assertIn('Codex settings applied:', first.stdout)
        with open(config, 'rb') as stream:
            projected = stream.read()
        self.assertIn(original.encode(), projected)
        self.assertIn(b'approval_policy = "never"', projected)
        self.assertIn(b'sandbox_mode = "danger-full-access"', projected)
        self.assertIn(b'model = "fixture-model"', projected)
        second = self.run_script('install.sh', '--provider', 'codex', extra_env=env)
        self.assertIn('Codex settings already current:', second.stdout)
        with open(config, 'rb') as stream:
            self.assertEqual(stream.read(), projected)
        self.run_script('uninstall.sh', '--provider', 'codex', extra_env=env)
        with open(config, 'rb') as stream:
            self.assertEqual(stream.read(), projected)
        self.assertEqual({'.system': None, 'local-skill': None}, _route(self.home))

    @unittest.skipUnless(shutil.which('codex'), 'native Codex required for selected lifecycle check')
    def test_codex_settings_refusal_preserves_config_and_still_installs_resources(self):
        if type(self) is not InstallerWiring:
            self.skipTest('selected Codex lifecycle is exercised by the wiring fixture')
        binaries = os.path.join(self.tmp, 'bin')
        os.makedirs(binaries)
        os.symlink(shutil.which('codex'), os.path.join(binaries, 'codex'))
        config = os.path.join(self.home, '.codex/config.toml')
        original = 'default_permissions = ":workspace"\n'
        with open(config, 'w') as stream:
            stream.write(original)
        result = self.run_script('install.sh', '--provider', 'codex',
                                 extra_env={'PATH': binaries + ':' + SAFE_PATH})
        self.assertIn('reconcile it explicitly', result.stderr)
        self.assertNotIn('Done:', result.stdout)
        with open(config) as stream:
            self.assertEqual(stream.read(), original)
        self.assertTrue(os.path.islink(os.path.join(self.home, '.codex/AGENTS.md')))
        self.assertTrue(os.path.islink(os.path.join(self.home, '.codex/skills/architect')))


class ClaudeSettingsLifecycle(InstallerWiring):
    """install.sh applies the tracked Claude settings only through an approved plan."""

    def read(self):
        with open(self.settings, "rb") as fh:
            return fh.read()

    def plan_id(self):
        proc = subprocess.run([sys.executable, os.path.join(self.copy, "providers", "claude", "settings.py"),
                               "check", "--side", "wsl", self.settings], capture_output=True, text=True)
        match = re.search(r"(?m)^plan id: ([0-9a-f]{12})$", proc.stdout)
        self.assertIsNotNone(match, proc.stdout + proc.stderr)
        return match.group(1)

    def test_invalid_local_input_refuses_before_link_creation(self):
        before = self.read()
        paths_before = _snapshot(self.home)
        local = os.path.join(os.path.dirname(self.copy), "config.local.json")
        with open(local, "w", encoding="utf-8") as stream:
            json.dump({"claude": {"unknown-field": "synthetic-private-marker"}}, stream)
        result = subprocess.run(
            ["bash", os.path.join(self.copy, "scripts", "install.sh"), "--provider", "claude", "--platform", "both"],
            env={"HOME": self.home, "PATH": SAFE_PATH, "TMPDIR": self.tmp},
            capture_output=True, text=True, timeout=60,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("synthetic-private-marker", result.stdout + result.stderr)
        self.assertEqual(self.read(), before)
        self.assertEqual(_snapshot(self.home), paths_before)
        self.assertFalse(os.path.lexists(os.path.join(self.home, ".claude", "CLAUDE.md")))

    def test_settings_are_applied_only_through_the_approved_plan(self):
        with open(self.tracked, encoding="utf-8") as fh:
            live = json.load(fh)
        live["model"] = "sonnet"
        live["theme"] = "dark"
        with open(self.settings, "w", encoding="utf-8") as fh:
            json.dump(live, fh, indent=2)
        before = self.read()

        refused = self.run_script("install.sh", "--provider", "claude")
        self.assertIn("--approve", refused.stdout + refused.stderr)
        self.assertEqual(before, self.read(), "an unapproved plan wrote settings")

        self.run_script("install.sh", "--provider", "claude", "--approve", self.plan_id())
        applied = json.loads(self.read())
        self.assertEqual("fixture-model", applied["model"])
        self.assertEqual("dark", applied["theme"], "Claude Code's own key was not kept")

        settled = self.read()
        again = self.run_script("install.sh", "--provider", "claude")
        self.assertIn("no changes", again.stdout)
        self.assertEqual(settled, self.read())

        removed = self.run_script("uninstall.sh", "--provider", "claude")
        self.assertIn("left in place", removed.stdout)
        self.assertEqual(settled, self.read(), "uninstall must never strip the owned keys")


class ProviderLifecycle(InstallerWiring):
    def compatible_profile(self):
        with open(os.path.join(ST.AGENTS, 'tests/providers/pi/endpoint-profiles.json')) as stream:
            entry = json.load(stream)['profiles']['arbitrary-chat']
        entry['credential'] = 'secrets/primary.key'
        return entry

    def test_missing_windows_cannot_report_selected_install_success(self):
        self.prepare_runtime()
        result = self.lifecycle('install', '--runtime')
        self.assertNotEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('Windows side skipped', result.stderr)
        self.assertNotIn('Done:', result.stdout)
        self.assertTrue(os.path.islink(os.path.join(self.home, '.pi/agent/AGENTS.md')))

    def test_missing_windows_cannot_report_selected_uninstall_success(self):
        self.prepare_runtime()
        self.assert_partial_operation(self.lifecycle('install', '--runtime'))
        agent = os.path.join(self.home, '.pi/agent')
        foreign = os.path.join(agent, 'foreign.md')
        with open(foreign, 'w') as stream: stream.write('keep')
        result = self.lifecycle('uninstall')
        self.assertFalse(os.path.lexists(os.path.join(agent, 'AGENTS.md')))
        self.assertFalse(os.path.lexists(os.path.join(self.home, '.local/bin/pi-sot')))
        with open(foreign) as stream: self.assertEqual(stream.read(), 'keep')
        self.assertNotEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('Windows side skipped', result.stderr)
        self.assertNotIn('Done:', result.stdout)

    def test_missing_key_allows_install_but_launch_refuses_without_mutation(self):
        self.prepare_runtime()
        os.unlink(os.path.join(self.tmp, 'repo/secrets/primary.key'))
        self.assert_partial_operation(self.lifecycle('install', '--runtime'))
        before = _snapshot(self.home)
        launcher = os.path.join(self.home, '.local/bin/pi-sot')
        result = subprocess.run([launcher], env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('credential file missing', result.stderr)
        self.assertEqual(_snapshot(self.home), before)

    def test_windows_unicode_link_queue_selects_utf8_before_commands(self):
        native_home = os.path.join(self.tmp, 'windows-home')
        os.makedirs(os.path.join(native_home, 'AppData/Local/Temp'))
        script = r'''powershell.exe() {
          if [[ "$*" == *GetFolderPath* ]]; then printf 'C:\\Users\\Тестовый пользователь\r\n'; fi
        }
        cmd.exe() { return 1; }
        timeout() { shift; "$@"; }
        wslpath() {
          if [[ "$1" == -u ]]; then printf '%s\n' "$FIXTURE_WIN_HOME";
          else printf 'D:\\Source\\%s\n' "${2##*/}"; fi
        }
        export -f powershell.exe cmd.exe wslpath timeout
        exec bash "$1" --provider shared --platform windows
        '''
        env = {'HOME': self.home, 'PATH': SAFE_PATH, 'TMPDIR': self.tmp,
               'FIXTURE_WIN_HOME': native_home}
        result = subprocess.run(['bash', '-c', script, 'fixture',
                                 os.path.join(self.copy, 'scripts/install.sh')],
                                env=env, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Queued NT links', result.stdout, result.stdout + result.stderr)
        batch = os.path.join(native_home, 'AppData/Local/Temp/agents-sot-links.cmd')
        with open(batch, 'rb') as stream: raw = stream.read()
        self.assertNotIn(b'\n', raw.replace(b'\r\n', b''))
        commands = raw.decode('utf-8').splitlines()
        self.assertEqual(commands[:2], ['@echo off', 'chcp 65001 >nul || exit /b 1'])
        self.assertIn('Тестовый пользователь', commands[2])
        self.assertTrue(commands[2].startswith('mklink '))
        self.assertFalse(os.path.exists(os.path.join(native_home, '.agents/AGENTS.md')))

    def test_unconfigured_runtime_installs_and_version_works_without_projection(self):
        self.prepare_runtime()
        with open(os.path.join(self.copy, 'providers/pi/runtime/profiles.json'), 'w') as stream:
            json.dump({'active': None, 'profiles': {}}, stream)
        shutil.rmtree(os.path.join(self.tmp, 'repo/secrets'))
        self.assert_partial_operation(self.lifecycle('install', '--runtime'))
        agent = os.path.join(self.home, '.pi/agent')
        for name in ('auth.json', 'models.json', 'agents-sot-state.json'):
            self.assertFalse(os.path.exists(os.path.join(agent, name)))
        launcher = os.path.join(self.home, '.local/bin/pi-sot')
        before = _snapshot(self.home)
        result = subprocess.run([launcher, '--version'], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([launcher], env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unconfigured', result.stderr)
        self.assertEqual(_snapshot(self.home), before)

    def test_projection_collision_refuses_before_runtime_or_wiring(self):
        self.prepare_runtime()
        agent = os.path.join(self.home, '.pi/agent')
        os.makedirs(agent)
        agent = os.path.join(agent, 'profiles/primary')
        os.makedirs(agent)
        auth = os.path.join(agent, 'auth.json')
        original = '{"deepseek":{"type":"api_key","key":"synthetic-foreign"}}'
        with open(auth, 'w') as stream: stream.write(original)
        before = _snapshot(self.home)
        result = self.lifecycle('install', '--runtime')
        self.assertNotEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertRegex(result.stderr, 'collision|foreign profile')
        self.assertEqual(_snapshot(self.home), before)
        with open(auth) as stream: self.assertEqual(stream.read(), original)
        self.assertFalse(os.path.exists(self.record), 'preflight must precede npm')

    def test_invalid_catalog_removes_only_new_owned_runtime(self):
        self.assert_new_runtime_refusal({'model': 'missing-model'}, 'model unavailable')

    def test_custom_structure_refuses_before_runtime_or_wiring(self):
        self.prepare_runtime()
        profile_file = os.path.join(self.copy, 'providers/pi/runtime/profiles.json')
        with open(profile_file) as stream:
            data = json.load(stream)
        data['active'] = 'compatible-fixture'
        data['profiles'][data['active']] = self.compatible_profile()
        data['profiles'][data['active']]['endpoint'] = ''
        with open(profile_file, 'w') as stream:
            json.dump(data, stream)
        before = _snapshot(self.home)
        result = self.lifecycle('install', '--runtime')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('requires explicit endpoint and API', result.stderr)
        self.assertEqual(_snapshot(self.home), before)
        self.assertFalse(os.path.exists(self.record))

    def test_missing_native_custom_schema_cleans_only_new_runtime(self):
        entry = self.compatible_profile()
        self.assert_new_runtime_refusal(entry, 'model-config.js')

    def test_invalid_api_removes_only_new_owned_runtime(self):
        self.assert_new_runtime_refusal({'api': 'anthropic-messages'}, 'API does not match')

    def test_unsupported_thinking_level_removes_only_new_owned_runtime(self):
        self.assert_new_runtime_refusal({'thinking': 'xhigh'}, 'thinking level xhigh unsupported')

    def assert_new_runtime_refusal(self, patch, error):
        self.prepare_runtime()
        with open(os.path.join(self.copy, 'providers/pi/runtime/profiles.json')) as stream: data = json.load(stream)
        data['profiles'][data['active']].update(patch)
        with open(os.path.join(self.copy, 'providers/pi/runtime/profiles.json'), 'w') as stream: json.dump(data, stream)
        prefix = os.path.join(self.home, '.local/share/pi-sot')
        os.makedirs(prefix)
        foreign = os.path.join(prefix, 'foreign.txt')
        with open(foreign, 'w') as stream: stream.write('keep')
        result = self.lifecycle('install', '--runtime')
        self.assertNotEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn(error, result.stderr)
        self.assertFalse(os.path.exists(os.path.join(prefix, 'node_modules/@earendil-works/pi-coding-agent')))
        self.assertFalse(os.path.exists(os.path.join(prefix, '.agents-sot-owner')))
        self.assertFalse(os.path.lexists(os.path.join(self.home, '.pi/agent')))
        with open(foreign) as stream: self.assertEqual(stream.read(), 'keep')
        with open(self.record) as stream: records = [json.loads(line) for line in stream]
        self.assertEqual(records, [{'npm':'ci'}], 'no native package registration')

    def test_invalid_catalog_preserves_preexisting_owned_runtime(self):
        self.prepare_runtime()
        self.assert_partial_operation(self.lifecycle('install', '--runtime'))
        before = _snapshot(self.home)
        with open(self.record) as stream: operations = stream.read()
        with open(os.path.join(self.copy, 'providers/pi/runtime/profiles.json')) as stream: data = json.load(stream)
        data['profiles'][data['active']]['model'] = 'missing-model'
        with open(os.path.join(self.copy, 'providers/pi/runtime/profiles.json'), 'w') as stream: json.dump(data, stream)
        result = self.lifecycle('install', '--runtime')
        self.assertNotEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('model unavailable', result.stderr)
        self.assertEqual(_snapshot(self.home), before)
        with open(self.record) as stream: records = [json.loads(line) for line in stream]
        self.assertEqual(records[len(operations.splitlines()):], [{'npm': 'ci'}],
                         'the locked install runs before catalog validation; the owned runtime survives')
        self.assertTrue(os.path.isfile(os.path.join(self.home, '.local/share/pi-sot/.agents-sot-owner')))

    def prepare_runtime(self):
        self.record = os.path.join(self.tmp, 'operations.jsonl')
        self.runtime_node = os.path.join(self.home, '.nvm/versions/node/v24.8.0/bin')
        os.makedirs(self.runtime_node)
        os.symlink(shutil.which('node', path=SAFE_PATH), os.path.join(self.runtime_node, 'node'))
        self.cli_source = os.path.join(self.tmp, 'cli.js')
        with open(self.cli_source, 'w') as stream:
            stream.write("const fs=require('fs'); fs.appendFileSync(process.env.PI_TEST_RECORD, JSON.stringify({args:process.argv.slice(2)})+'\\n'); if(process.env.PI_TEST_FAIL) process.exit(7); if(process.argv[2]==='install'||process.argv[2]==='remove'){const path=require('path'),file=path.join(process.env.PI_CODING_AGENT_DIR,'settings.json'),data=fs.existsSync(file)?JSON.parse(fs.readFileSync(file)):{};data.packages=(data.packages??[]).filter(x=>x!==process.argv[3]);if(process.argv[2]==='install')data.packages.push(process.argv[3]);fs.writeFileSync(file,JSON.stringify(data));}\n")
        npm = os.path.join(self.runtime_node, 'npm')
        os.symlink(sys.executable, npm)
        for operation in ('ci', 'uninstall'):
            with open(os.path.join(self.tmp, operation), 'w') as stream:
                stream.write("""import os,sys,json,shutil
from pathlib import Path
operation=Path(sys.argv[0]).name
with open(os.environ['PI_TEST_RECORD'], 'a') as out: out.write(json.dumps({'npm':operation})+'\\n')
prefix=Path(sys.argv[2]);package=prefix/'node_modules/@earendil-works/pi-coding-agent'
if operation=='ci':
    if os.environ.get('PI_TEST_CI_FAIL'):
        partial=prefix/'node_modules/partial';partial.mkdir(parents=True,exist_ok=True);(partial/'x').write_text('partial');sys.exit(7)
    cli=package/'dist/bundle/cli.js';cli.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(os.environ['PI_TEST_CLI'],cli)
    args=package/'dist/cli/args.js';args.parent.mkdir(exist_ok=True)
    args.write_text("export function parseArgs(){return {}}")
    storage=package/'dist/core/settings-manager.js';storage.parent.mkdir(exist_ok=True)
    storage.write_text("import fs from 'node:fs';import path from 'node:path';export class FileSettingsStorage {constructor(cwd,dir){this.file=path.join(dir,'settings.json')}withLock(scope,fn){const next=fn(fs.existsSync(this.file)?fs.readFileSync(this.file,'utf8'):undefined);if(next!==undefined)fs.writeFileSync(this.file,next)}}")
    locked=json.loads((prefix/'package.json').read_text())['dependencies']['@earendil-works/pi-coding-agent']
    (package/'package.json').write_text(json.dumps({'version':locked}))
    catalog=prefix/'node_modules/@earendil-works/pi-ai/dist/providers/data';catalog.mkdir(parents=True,exist_ok=True)
    data={'models':{'flash':{'id':'deepseek-flash','api':'openai-completions'},'other':{'id':'fixture-model','api':'openai-completions'}}}
    for provider in ('deepseek','fixture'): (catalog/(provider+'.json')).write_text(json.dumps(data))
    (catalog.parent.parent/'index.js').write_text("export function getSupportedThinkingLevels(){return ['off','low','high','max']}")
else: shutil.rmtree(package)
""")
        self.env = {'HOME': self.home, 'PATH': SAFE_PATH, 'TMPDIR': self.tmp,
                    'PI_TEST_RECORD': self.record, 'PI_TEST_CLI': self.cli_source}
        secret = os.path.join(self.tmp, 'repo/secrets')
        os.makedirs(secret, exist_ok=True)
        for name in ('primary', 'fixture'):
            with open(os.path.join(secret, name+'.key'), 'w') as stream: stream.write('synthetic-key')

    def lifecycle(self, operation, *args):
        return subprocess.run(['bash', os.path.join(self.copy, 'scripts', operation+'.sh'),
                               '--provider', 'pi', '--platform', 'both', *args], env=self.env,
                              capture_output=True, text=True, timeout=30, cwd=self.tmp)

    def assert_partial_operation(self, result):
        self.assertEqual(result.returncode, 1, result.stdout+result.stderr)
        self.assertIn('Windows side skipped', result.stderr)
        self.assertNotIn('Done:', result.stdout)

    def test_runtime_acquisition_uses_path_node_without_an_nvm_install(self):
        self.prepare_runtime()
        portable=os.path.join(self.tmp,'portable-bin')
        shutil.move(self.runtime_node,portable)
        self.env['PATH']=portable+os.pathsep+SAFE_PATH
        with open(self.cli_source) as stream:cli=stream.read()
        with open(self.cli_source,'w') as stream:stream.write(cli.replace('args:process.argv.slice(2)', 'args:process.argv.slice(2),telemetry:process.env.PI_TELEMETRY'))
        capture=os.path.join(self.tmp,'npm-argv.json')
        ci=os.path.join(self.tmp,'ci')
        with open(ci) as stream:code=stream.read()
        with open(ci,'w') as stream:stream.write(code.replace('operation=Path(sys.argv[0]).name',
            'Path('+repr(capture)+').write_text(json.dumps(sys.argv))\noperation=Path(sys.argv[0]).name'))
        result=self.lifecycle('install','--runtime')
        self.assert_partial_operation(result)
        with open(capture) as stream:argv=json.load(stream)
        self.assertIn('--engine-strict',argv)
        with open(self.record) as stream:operations=[json.loads(line) for line in stream]
        self.assertEqual(next(row for row in operations if 'args' in row)['telemetry'],'0')
        self.assertTrue(os.path.isfile(os.path.join(self.home,'.local/bin/pi-sot')))
        self.assert_partial_operation(self.lifecycle('uninstall','--runtime'))

    def test_runtime_order_and_foreign_state(self):
        import json
        self.prepare_runtime()
        prefix = os.path.join(self.home, '.local/share/pi-sot')
        os.makedirs(prefix)
        foreign = os.path.join(prefix, 'foreign.txt')
        with open(foreign, 'w') as stream: stream.write('keep')
        result = self.lifecycle('install', '--runtime')
        self.assert_partial_operation(result)
        self.assertTrue(os.path.isfile(os.path.join(prefix, 'package-lock.json')),
                        'the locked installation artifact must land in the runtime prefix')
        result = self.lifecycle('uninstall', '--runtime')
        self.assert_partial_operation(result)
        with open(self.record) as stream: records = [json.loads(line) for line in stream]
        self.assertEqual([r.get('npm') or r['args'][0] for r in records], ['ci', 'install', 'install', 'remove', 'remove'])
        self.assertTrue(os.path.isfile(foreign))
        self.assertFalse(os.path.lexists(os.path.join(self.home, '.pi/agent/AGENTS.md')))

    def test_profile_changes_follow_managed_launch(self):
        import json
        self.prepare_runtime()
        self.assert_partial_operation(self.lifecycle('install', '--runtime'))
        launcher = os.path.join(self.home, '.local/bin/pi-sot')
        config_path = os.path.join(self.copy, 'providers/pi/runtime/profiles.json')
        def launch():
            return subprocess.run(['bash', launcher], env=self.env,
                                  capture_output=True, text=True, timeout=30)
        self.assertEqual(launch().returncode, 0)
        with open(config_path, 'w') as stream:
            json.dump({'active':'fixture-profile','profiles':{'fixture-profile':{'provider':'fixture','model':'fixture-model','credential':'secrets/fixture.key','endpoint':'http://127.0.0.1:9999','api':'openai-completions'}}}, stream)
        self.assertEqual(launch().returncode, 0)
        with open(self.record) as stream: records = [json.loads(line) for line in stream]
        self.assertEqual(records[-1]['args'][:4], ['--provider', 'fixture', '--model', 'fixture-model'])
        auth_path = os.path.join(self.home, '.pi/agent/profiles/fixture-profile/auth.json')
        with open(auth_path) as stream: auth = json.load(stream)
        self.assertNotIn('deepseek', auth)
        self.assertIn('fixture.key', auth['fixture']['key'])
        with open(os.path.join(self.home, '.pi/agent/profiles/fixture-profile/models.json')) as stream:
            self.assertEqual(json.load(stream)['providers']['fixture']['baseUrl'], 'http://127.0.0.1:9999')
        before = _snapshot(self.home)
        with open(config_path, 'w') as stream: json.dump({'active':'missing','profiles':{'fixture-profile':{'provider':'fixture','model':'fixture-model','credential':'secrets/fixture.key'}}}, stream)
        self.assertNotEqual(launch().returncode, 0)
        self.assertEqual(_snapshot(self.home), before)
        with open(self.record) as stream: self.assertEqual([json.loads(line) for line in stream], records)

    def test_invalid_registration_cannot_be_hidden_by_later_config(self):
        registry = os.path.join(self.copy, 'lifecycle/providers.conf.sh')
        with open(registry, 'a') as stream:
            stream.write('\nregister_provider fixture ../foreign AGENTS.md none generic\nregister_provider valid .valid AGENTS.md none generic\n')
        before = _snapshot(self.home)
        result = subprocess.run(['bash', os.path.join(self.copy, 'scripts/install.sh')], env={'HOME':self.home,'PATH':SAFE_PATH}, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(_snapshot(self.home), before)

    def test_invalid_thinking_level_refuses_without_mutation(self):
        profile_path = os.path.join(self.copy, 'providers/pi/runtime/profiles.json')
        with open(profile_path) as stream: data = json.load(stream)
        data['profiles'][data['active']]['thinking'] = 'turbo'
        with open(profile_path, 'w') as stream: json.dump(data, stream)
        before = _snapshot(self.home)
        result = subprocess.run(['bash', os.path.join(self.copy, 'scripts/install.sh'), '--provider', 'pi', '--platform', 'both'], env={'HOME':self.home,'PATH':SAFE_PATH,'TMPDIR':self.tmp}, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('invalid thinking level', result.stderr)
        self.assertEqual(_snapshot(self.home), before)

    def test_install_lock_matches_pinned_release(self):
        with open(os.path.join(self.copy, 'lifecycle/providers.conf.sh')) as stream:
            version = re.search(r"^PI_PACKAGE='[^']+@([^']+)'", stream.read(), re.M).group(1)
        with open(os.path.join(self.copy, 'providers/pi/runtime/install-lock/package.json')) as stream:
            root = json.load(stream)
        with open(os.path.join(self.copy, 'providers/pi/runtime/install-lock/package-lock.json')) as stream:
            lock = json.load(stream)
        name = '@earendil-works/pi-coding-agent'
        packages = lock['packages']
        self.assertEqual(lock['lockfileVersion'], 3)
        self.assertEqual(root['version'], version)
        self.assertEqual(root['dependencies'], {name: version})
        self.assertEqual(packages['']['version'], version)
        self.assertEqual(packages['']['dependencies'], {name: version})
        for entry in (name, '@earendil-works/pi-ai'):
            self.assertEqual(packages['node_modules/'+entry]['version'], version,
                             entry+' must stay on the pinned release; regenerate the install lock after a pin bump')
        self.assertIn('integrity', packages['node_modules/@earendil-works/pi-ai'])

    def test_runtime_upgrade_replaces_stale_pinned_runtime(self):
        self.prepare_runtime()
        self.assert_partial_operation(self.lifecycle('install', '--runtime'))
        prefix = os.path.join(self.home, '.local/share/pi-sot')
        registry = os.path.join(self.copy, 'lifecycle/providers.conf.sh')
        with open(registry) as stream: config = stream.read()
        with open(registry, 'w') as stream: stream.write(re.sub(r"@[^'@]+'", "@9.9.9'", config, count=1))
        lock = os.path.join(self.copy, 'providers/pi/runtime/install-lock/package.json')
        with open(lock) as stream: data = json.load(stream)
        data['version'] = '9.9.9'; data['dependencies']['@earendil-works/pi-coding-agent'] = '9.9.9'
        with open(lock, 'w') as stream: json.dump(data, stream)
        self.assert_partial_operation(self.lifecycle('install', '--runtime'))
        with open(os.path.join(prefix, 'node_modules/@earendil-works/pi-coding-agent/package.json')) as stream:
            self.assertEqual(json.load(stream)['version'], '9.9.9', 'a bumped pin must replace the stale runtime')
        with open(self.record) as stream: records = [json.loads(line) for line in stream]
        self.assertEqual([r.get('npm') or r['args'][0] for r in records], ['ci', 'install', 'install', 'ci', 'install'])

    def test_locked_runtime_install_uninstall_reinstall(self):
        self.prepare_runtime()
        prefix = os.path.join(self.home, '.local/share/pi-sot')
        os.makedirs(prefix)
        foreign = os.path.join(prefix, 'foreign.txt')
        with open(foreign, 'w') as stream: stream.write('keep')
        self.assert_partial_operation(self.lifecycle('install', '--runtime'))
        self.assert_partial_operation(self.lifecycle('uninstall', '--runtime'))
        self.assertFalse(os.path.exists(os.path.join(prefix, 'node_modules')))
        self.assertFalse(os.path.exists(os.path.join(prefix, '.agents-sot-owner')))
        self.assert_partial_operation(self.lifecycle('install', '--runtime'))
        self.assertTrue(os.path.isfile(os.path.join(prefix, 'node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js')))
        with open(foreign) as stream: self.assertEqual(stream.read(), 'keep')

    def test_acquired_runtime_projects_selected_catalog_model(self):
        self.prepare_runtime()
        self.assert_partial_operation(self.lifecycle('install', '--runtime'))
        models_file = os.path.join(self.home, '.pi/agent/profiles/primary/models.json')
        self.assertTrue(os.path.isfile(models_file), 'runtime acquisition must project the selected pinned model')
        with open(models_file) as stream:
            models = json.load(stream)['providers']['deepseek']['models']
        self.assertEqual([model['id'] for model in models], ['deepseek-flash'])

    def test_runtime_reapplication_preserves_native_preferences_and_updates_retry_policy(self):
        self.prepare_runtime()
        self.assert_partial_operation(self.lifecycle('install', '--runtime'))
        settings_file = os.path.join(self.home, '.pi/agent/profiles/primary/settings.json')
        with open(settings_file) as stream: settings = json.load(stream)
        with open(os.path.join(self.copy, 'providers/pi/runtime/retry-policy.json')) as stream: policy = json.load(stream)
        self.assertEqual(settings['retry'], policy)
        settings.update(theme='synthetic-theme', defaultModel='synthetic-model')
        settings['retry']['provider'] = {'maxRetries': 0}
        with open(settings_file, 'w') as stream: json.dump(settings, stream)
        policy['baseDelayMs'] = 5000
        with open(os.path.join(self.copy, 'providers/pi/runtime/retry-policy.json'), 'w') as stream: json.dump(policy, stream)
        self.assert_partial_operation(self.lifecycle('install', '--runtime'))
        with open(settings_file) as stream: updated = json.load(stream)
        self.assertEqual(updated, {**settings, 'retry': {**policy, 'provider': {'maxRetries': 0}}})
        self.assert_partial_operation(self.lifecycle('uninstall', '--runtime'))
        with open(settings_file) as stream: removed = json.load(stream)
        self.assertEqual(removed, {**updated, 'packages': []})
        self.assert_partial_operation(self.lifecycle('install', '--runtime'))
        with open(settings_file) as stream: self.assertEqual(json.load(stream), updated)

    def test_failed_first_locked_install_leaves_retryable_prefix(self):
        self.prepare_runtime()
        prefix = os.path.join(self.home, '.local/share/pi-sot')
        os.makedirs(prefix)
        foreign = os.path.join(prefix, 'foreign.txt')
        with open(foreign, 'w') as stream: stream.write('keep')
        self.env['PI_TEST_CI_FAIL'] = '1'
        result = self.lifecycle('install', '--runtime')
        self.assertNotEqual(result.returncode, 0, result.stdout+result.stderr)
        for managed in ('node_modules', 'package.json', 'package-lock.json', '.agents-sot-owner'):
            self.assertFalse(os.path.exists(os.path.join(prefix, managed)),
                             'a failed first install must not leave ' + managed)
        self.assertFalse(os.path.exists(os.path.join(self.home, '.pi/agent')))
        del self.env['PI_TEST_CI_FAIL']
        self.assert_partial_operation(self.lifecycle('install', '--runtime'))
        with open(foreign) as stream: self.assertEqual(stream.read(), 'keep')

    def test_unowned_runtime_artifacts_refuse_before_mutation(self):
        self.prepare_runtime()
        prefix = os.path.join(self.home, '.local/share/pi-sot')
        os.makedirs(prefix)
        foreign = os.path.join(prefix, 'foreign.txt')
        with open(foreign, 'w') as stream: stream.write('keep')
        for managed in ('node_modules', 'package.json', 'package-lock.json'):
            target = os.path.join(prefix, managed)
            if managed == 'node_modules': os.makedirs(target)
            else:
                with open(target, 'w') as stream: stream.write('foreign')
            result = self.lifecycle('install', '--runtime')
            self.assertNotEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('existing unowned Pi runtime artifact left alone', result.stderr)
            self.assertFalse(os.path.exists(self.record), 'the ownership gate must precede npm')
            self.assertFalse(os.path.exists(os.path.join(prefix, '.agents-sot-owner')))
            self.assertEqual(sorted(os.listdir(prefix)), sorted([managed, 'foreign.txt']))
            if managed == 'node_modules': shutil.rmtree(target)
            else: os.unlink(target)
        broken = os.path.join(prefix, 'package-lock.json')
        os.symlink('missing-target', broken)
        result = self.lifecycle('install', '--runtime')
        self.assertNotEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('existing unowned Pi runtime artifact left alone', result.stderr)
        self.assertFalse(os.path.exists(self.record))
        self.assertTrue(os.path.islink(broken))
        os.unlink(broken)
        self.assert_partial_operation(self.lifecycle('install', '--runtime'))
        with open(foreign) as stream: self.assertEqual(stream.read(), 'keep')

    def test_cleanup_failure_is_reported_not_hidden(self):
        self.prepare_runtime()
        prefix = os.path.join(self.home, '.local/share/pi-sot')
        os.makedirs(prefix)
        self.env['PI_TEST_CI_FAIL'] = '1'
        result = self.lifecycle_with_failing_cleanup('--runtime')
        self.assertNotEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('failed install cleanup failed', result.stderr)
        self.assertTrue(os.path.exists(os.path.join(prefix, 'node_modules')))
        self.assertFalse(os.path.exists(os.path.join(prefix, '.agents-sot-owner')))

    def lifecycle_with_failing_cleanup(self, *args):
        stub = ('rm() { case "$*" in *node_modules*) echo "stub: removing node_modules failed" >&2; return 1;; esac; command rm "$@"; }; export -f rm; ')
        return subprocess.run(['bash', '-c', stub+'exec bash "$@"', 'stub',
                               os.path.join(self.copy, 'scripts/install.sh'), '--provider', 'pi', '--platform', 'both', *args],
                              env=self.env, capture_output=True, text=True, timeout=30, cwd=self.tmp)

    def test_install_lock_generator_derives_package_json_from_pin(self):
        lock_dir = os.path.join(self.copy, 'providers/pi/runtime/install-lock')
        fake = os.path.join(self.tmp, 'fake-bin')
        os.makedirs(fake)
        os.symlink(sys.executable, os.path.join(fake, 'npm'))
        recorded = os.path.join(self.tmp, 'npm-args.json')
        with open(os.path.join(lock_dir, 'install'), 'w') as stream:
            stream.write("import json,os,sys\nopen(os.environ['PI_TEST_NPM_ARGS'],'w').write(json.dumps(sys.argv[1:]))\n")
        env = {'HOME': self.home, 'PATH': fake+':'+SAFE_PATH, 'TMPDIR': self.tmp, 'PI_TEST_NPM_ARGS': recorded}
        result = subprocess.run(['bash', os.path.join(lock_dir, 'generate.sh')], env=env, capture_output=True, text=True, cwd=self.tmp)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        with open(os.path.join(self.copy, 'lifecycle/providers.conf.sh')) as stream:
            spec = re.search(r"^PI_PACKAGE='([^']+)'", stream.read(), re.M).group(1)
        name, version = spec.rsplit('@', 1)
        with open(os.path.join(lock_dir, 'package.json')) as stream: derived = json.load(stream)
        self.assertEqual(derived, {'name': 'pi-sot-managed-install', 'version': version, 'private': True,
                                   'dependencies': {name: version}})
        with open(recorded) as stream:
            self.assertEqual(json.load(stream), ['--package-lock-only', '--ignore-scripts', '--no-audit', '--no-fund'])

    def test_selected_pi_uninstall_preserves_claude(self):
        self.run_script('install.sh')
        marker = os.path.join(self.home, '.claude', 'CLAUDE.md')
        original = os.readlink(marker)
        proc = subprocess.run(['bash', os.path.join(self.copy, 'scripts', 'uninstall.sh'),
                               '--provider', 'pi', '--platform', 'both'], env={'HOME': self.home, 'PATH': SAFE_PATH,
                               'TMPDIR': self.tmp}, capture_output=True, text=True)
        self.assert_partial_operation(proc)
        self.assertTrue(os.path.islink(marker), proc.stdout + proc.stderr)
        self.assertEqual(os.readlink(marker), original)

    def test_unknown_provider_refuses_without_mutation(self):
        before = _snapshot(self.home)
        proc = subprocess.run(['bash', os.path.join(self.copy, 'scripts', 'install.sh'),
                               '--provider', 'missing'], env={'HOME': self.home, 'PATH': SAFE_PATH,
                               'TMPDIR': self.tmp}, capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(_snapshot(self.home), before)

    def test_registry_extension_and_target_change(self):
        registry = os.path.join(self.copy, 'lifecycle', 'providers.conf.sh')
        with open(registry, 'a') as stream:
            stream.write("\nregister_provider fixture .fixture AGENTS.md none generic\n")
        def run(op):
            return subprocess.run(['bash', os.path.join(self.copy, 'scripts', op+'.sh'),
                                   '--provider', 'fixture', '--platform', 'both'], env={'HOME': self.home, 'PATH': SAFE_PATH,
                                   'TMPDIR': self.tmp}, capture_output=True, text=True)
        self.assert_partial_operation(run('install'))
        self.assertTrue(os.path.islink(os.path.join(self.home, '.fixture', 'AGENTS.md')))
        self.assert_partial_operation(run('uninstall'))
        self.assertFalse(os.path.lexists(os.path.join(self.home, '.fixture', 'AGENTS.md')))
        with open(registry) as stream: config = stream.read()
        with open(registry, 'w') as stream: stream.write(config.replace('.fixture AGENTS.md', '.fixture-new AGENTS.md'))
        self.assert_partial_operation(run('install'))
        self.assertTrue(os.path.islink(os.path.join(self.home, '.fixture-new', 'AGENTS.md')))
        self.assert_partial_operation(run('uninstall'))

    def test_shared_resource_paths_follow_descriptor(self):
        registry = os.path.join(self.copy, 'lifecycle/providers.conf.sh')
        with open(registry) as stream: config = stream.read()
        anchor = 'register_provider shared .agents '
        self.assertEqual(config.count(anchor), 1)
        with open(registry, 'w') as stream: stream.write(config.replace(anchor, 'register_provider shared .shared-fixture '))
        self.run_script('install.sh')
        target = os.path.join(self.home, '.shared-fixture')
        self.assertTrue(os.path.islink(os.path.join(target, 'agent-ignore')))
        with open(os.path.join(target, 'ripgreprc')) as stream:
            self.assertEqual(stream.read(), '--ignore-file='+target+'/agent-ignore\n')
        with open(os.path.join(self.home, '.bashrc')) as stream:
            self.assertIn('$HOME/.shared-fixture/ripgreprc', stream.read())
        self.assertFalse(os.path.exists(os.path.join(self.home, '.agents/ripgreprc')))
        result = subprocess.run(['bash', os.path.join(self.copy, 'scripts/uninstall.sh'), '--provider', 'shared', '--platform', 'both'],
                                env={'HOME':self.home,'PATH':SAFE_PATH,'TMPDIR':self.tmp}, capture_output=True, text=True)
        self.assert_partial_operation(result)
        self.assertFalse(os.path.lexists(os.path.join(target, 'agent-ignore')))
        self.assertFalse(os.path.exists(os.path.join(target, 'ripgreprc')))

    def test_runtime_capability_refuses_before_mutation(self):
        before = _snapshot(self.home)
        proc = subprocess.run(['bash', os.path.join(self.copy, 'scripts', 'install.sh'),
                               '--provider', 'claude', '--runtime'],
                              env={'HOME': self.home, 'PATH': SAFE_PATH, 'TMPDIR': self.tmp},
                              capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(_snapshot(self.home), before)


if __name__ == "__main__":
    unittest.main()
