"""Pi-specific rules and context ownership through the real Python boundary."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / 'providers/pi/permissions/gate.py'
CWD = str(ROOT)


def call(tool, value, cwd=CWD, env=None):
    inp = {'command': value} if tool == 'bash' else {'path': value}
    return subprocess.run([sys.executable, str(GATE)], input=json.dumps(
        {'cwd': cwd, 'event': {'toolName': tool, 'input': inp}}),
        text=True, capture_output=True, env=env)


class PiGate(unittest.TestCase):
    def expect(self, tool, value, allow, cwd=CWD, env=None):
        result = call(tool, value, cwd, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision['pi_gate'], 1)
        self.assertEqual(decision['allow'], allow, (value, decision))

    def test_readonly_and_plain_switch(self):
        for cmd in ['git status', 'git log --oneline', 'git diff', 'git fetch',
                    'git -C sub status', 'git switch main', 'git switch -c x',
                    'git stash list', 'git stash show', 'echo sudo']:
            with self.subTest(cmd=cmd): self.expect('bash', cmd, True)

    def test_git_writes_wrappers_and_segments(self):
        cmds = ['git add -A', 'git stage f', 'git -C sub add f', 'cd x && git add f',
                'true; git mv a b', 'git rm --cached f', 'git restore --staged f',
                'git reset', 'git reset --hard HEAD', 'git stash', 'git stash push -m x',
                'git commit -m x', 'git -c user.name=x commit', 'git rebase main',
                'git merge x', 'git cherry-pick x', 'git revert x', 'git am p.patch',
                'git push', 'git clean -fd', 'timeout 5 git push',
                'command git add f', 'GIT_DIR=x git commit -m y', 'git restore f',
                'git checkout -- f', 'git checkout f', 'git checkout main',
                'git switch -f main', 'git switch --discard-changes main', 'sudo ls']
        for cmd in cmds:
            with self.subTest(cmd=cmd): self.expect('bash', cmd, False)

    def test_scope_and_git_directory(self):
        for cmd in ['rm -rf /opt/pi-absent/x', 'rm -rf .git', 'rm -rf sub/.git']:
            self.expect('bash', cmd, False)
        self.expect('bash', 'rm -rf build', True)
        self.expect('write', '/etc/pi-absent', False)
        self.expect('write', 'build/ok.txt', True)

    def test_secret_paths_and_readers(self):
        paths = ['~/.ssh/id_x', '.env', '.env.local', 'secrets/x.key', 'sub/secrets/x',
                 '~/.aws/credentials', '~/.pi/agent/auth.json', 'ansible/.vault_pass',
                 r'C:\Users\x\.ssh\id', '/c/Users/x/.ssh/id', r'E:\repo\secrets\k']
        for path in paths:
            with self.subTest(path=path): self.expect('read', path, False)
        for path in ['docs/secrets.md', '.envrc']: self.expect('read', path, True)
        for cmd in ['cat ~/.ssh/id_x', 'grep -r k secrets/', 'head .env', 'cp .env /tmp/x']:
            self.expect('bash', cmd, False)
        self.expect('bash', 'ssh -i ~/.ssh/id_x host true', True)
        self.expect('write', 'secrets/new.key', False)
        self.expect('edit', '.env', False)

    def test_unknown_input(self):
        self.expect('bash', 'echo "unterminated', False)
        for cwd in ['', None, 'relative']:
            result = call('write', 'x', cwd)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('"allow": true', result.stdout)

    def test_context_ignores_claude_override(self):
        env = dict(os.environ, CLAUDE_PROJECT_DIR='/opt/pi-context-b')
        self.expect('bash', 'rm -rf build', True, env=env)
        self.expect('bash', 'rm -rf /opt/pi-context-b/x', False, env=env)
        self.expect('write', 'build/x', True, env=env)
        self.expect('write', '/opt/pi-context-b/x', False, env=env)

    def test_reused_guard_exception_is_not_allow(self):
        self.assertTrue(GATE.exists(), 'Pi gate feature missing')
        spec = importlib.util.spec_from_file_location('pi_gate', GATE)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with patch.object(module.bash_rm_guard, 'main', side_effect=RuntimeError('probe error')):
            with self.assertRaises(RuntimeError):
                module.decide({'cwd': CWD, 'event': {'toolName': 'bash', 'input': {'command': 'rm -rf build'}}})

    def test_probe(self):
        result = subprocess.run([sys.executable, str(GATE), '--probe', CWD], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['pi_gate'], 1); self.assertTrue(data['healthy'])
        self.assertTrue(all(not case['allow'] for case in data['cases']))


if __name__ == '__main__': unittest.main()
