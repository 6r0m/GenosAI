#!/usr/bin/env python3
"""Pi's instruction-derived rules around the unchanged shared scope guards."""
import contextlib
import io
import json
import os
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'permissions/guards'))
import bash_rm_guard
import repo_guard
from _paths import native, resolve

GIT_WRITES = set('add stage mv rm reset restore checkout commit rebase merge cherry-pick revert am push clean'.split())
READERS = set('cat less more head tail grep rg cp base64 xxd od strings sed awk nl'.split())
SECRET_PARTS = set('.ssh .gnupg .aws .kube .docker secrets'.split())


def secret(path, cwd):
    expanded = os.path.expanduser(native(path))
    if not os.path.isabs(expanded) and not re.match(r'^[a-zA-Z]:', expanded):
        expanded = os.path.join(native(cwd), expanded)
    for value in (expanded, resolve(os.path.normpath(expanded))):
        parts = value.replace('\\', '/').lower().split('/')
        name = parts[-1]
        if SECRET_PARTS.intersection(parts) or name in {'.vault_pass', '.env'} or name.startswith('.env.'):
            return True
        if any(owner in '/'.join(parts) for owner in
               ['.pi/agent/auth.json', '.codex/auth.json', '.claude/.credentials.json']):
            return True
    return False


def deny(reason):
    return {'pi_gate': 1, 'allow': False, 'reason': reason}


def reused(module, payload):
    output = io.StringIO()
    original = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        with contextlib.redirect_stdout(output):
            returned = module.main()
    finally:
        sys.stdin = original
    value = json.loads(output.getvalue()) if output.getvalue().strip() else returned
    if value is None or isinstance(value, int):
        value = {}
    decision = value.get('hookSpecificOutput', {})
    if decision.get('permissionDecision') == 'deny':
        return deny(decision.get('permissionDecisionReason', 'scope guard refused'))


def decide(envelope):
    cwd = envelope.get('cwd')
    if not isinstance(cwd, str) or not cwd.strip() or not os.path.isabs(native(cwd)) or not os.path.isdir(native(cwd)):
        raise ValueError('Pi context cwd must be an existing absolute directory')
    os.environ.pop('CLAUDE_PROJECT_DIR', None)
    event = envelope['event']
    tool, inp = event['toolName'], event['input']
    if not isinstance(inp, dict):
        raise ValueError('invalid tool input')
    if tool in {'read', 'edit', 'write', 'grep', 'find', 'ls'}:
        path = inp.get('path', '.') if tool in {'grep', 'find', 'ls'} else inp.get('path')
        if not isinstance(path, str) or not path:
            raise ValueError('missing tool path')
        if secret(path, cwd):
            return deny('protected secret path')
        if tool in {'edit', 'write'}:
            result = reused(repo_guard, {'cwd': cwd, 'tool_name': tool.title(), 'tool_input': {'file_path': path}})
            if result:
                return result
    elif tool == 'bash':
        command = inp.get('command')
        if not isinstance(command, str):
            raise ValueError('missing command')
        for segment in bash_rm_guard.split_segments(command):
            try:
                tokens = shlex.split(segment)
            except ValueError:
                return deny('cannot tokenize command')
            while tokens and re.fullmatch(r'[A-Za-z_]\w*=.*', tokens[0], re.S):
                tokens.pop(0)
            tokens = bash_rm_guard.strip_wrappers(tokens)
            if not tokens:
                continue
            name, args = os.path.basename(tokens[0]), tokens[1:]
            if name == 'sudo':
                return deny('system-wide operation requires operator authorization')
            if name == 'git':
                i = 0
                while i < len(args) and args[i].startswith('-'):
                    i += 2 if args[i] in {'-C', '-c', '--git-dir', '--work-tree', '--namespace', '--config-env'} else 1
                sub = args[i] if i < len(args) else ''
                rest = args[i + 1:]
                if sub in GIT_WRITES or (sub == 'stash' and (not rest or rest[0] not in {'list', 'show'})):
                    return deny('protected Git operation: ' + sub)
                if sub == 'switch' and any(x in {'-f', '--force', '--discard-changes'} or re.fullmatch(r'-[^-]*f[^-]*', x) for x in rest):
                    return deny('Git switch would discard working-tree changes')
            if name == 'rm' and any(bash_rm_guard.RECURSIVE_RE.match(x) for x in args):
                if any('.git' in x.replace('\\', '/').split('/') for x in bash_rm_guard.rm_targets(args)):
                    return deny('recursive removal of .git')
            if name in READERS and any(secret(x, cwd) for x in args if not x.startswith('-')):
                return deny('content reader targets a protected secret path')
        result = reused(bash_rm_guard, {'cwd': cwd, 'tool_name': 'Bash', 'tool_input': {'command': command}})
        if result:
            return result
    else:
        raise ValueError('unsupported gated tool')
    return {'pi_gate': 1, 'allow': True}


def probe(cwd):
    samples = [('bash', 'git add -A'), ('bash', 'git push'), ('bash', 'git restore x'),
               ('bash', 'sudo true'), ('bash', 'rm -rf .git'), ('bash', 'rm -rf /opt/pi-absent/x'),
               ('read', 'secrets/pi-absent.key'), ('write', '/etc/pi-absent')]
    cases = []
    for tool, value in samples:
        inp = {'command': value} if tool == 'bash' else {'path': value}
        cases.append({'tool': tool, **decide({'cwd': cwd, 'event': {'toolName': tool, 'input': inp}})})
    return {'pi_gate': 1, 'healthy': all(not case['allow'] for case in cases), 'cases': cases, 'interpreter': sys.executable}


if __name__ == '__main__':
    try:
        result = probe(sys.argv[2]) if sys.argv[1:2] == ['--probe'] else decide(json.load(sys.stdin))
        print(json.dumps(result))
    except Exception as exc:
        print('pi_gate: ' + str(exc), file=sys.stderr)
        sys.exit(1)
