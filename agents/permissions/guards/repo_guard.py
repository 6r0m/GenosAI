#!/usr/bin/env python
"""PreToolUse guard: file edits are allowed inside the working repo and a few
sanctioned scratch areas; everywhere else on disk is read-only.

Why this exists: Claude Code deny rules cannot carry allowlist exceptions
(a broad deny blocks even calls that match a narrower allow), so "edit only
inside my repos" cannot be written as a deny rule. A PreToolUse hook can
express it as a positive allowlist instead, and covers directories that were
never enumerated -- including ones that do not exist yet.

Scope: file tools only (Edit / Write / NotebookEdit). Bash-mediated writes are
not parsed here. Claude Code does apply Edit(//...) deny rules to file
operations it recognizes in Bash, including recognized file commands and
redirection targets - `touch` is refused under //etc/** and
//**/.claude/hooks/** while an unmatched path succeeds. It does not cover an
arbitrary subprocess such as Python or Node opening a file itself; those are
accepted limitations of this fail-open model. What the rules also cannot
express is "inside the repo only" - see below. Recursive deletes are separately
guarded for every path, by bash_rm_guard.py on PreToolUse.

Failure behaviour: fails OPEN on unexpected parsing or runtime errors. Invalid
local configuration instead produces an explicit deny. An unexpected error exits 0
with no decision so a bug here can never wedge a session. Be honest about the
cost: for file edits the Edit(//...) deny rules do cover the paths they name,
but they enumerate specific locations rather than expressing "inside the repo
only" - that is the gap this guard fills, and if it does not run, the gap is
open again. There is no fail-closed layer that reproduces this guard's scope.

SOT: agents/permissions/guards/, registered for
both WSL and Windows by a hook command that resolves the repo path per platform
and launches this guard through ../run-guard.sh.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
from _paths import native, resolve
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import ConfigError, load

# Sanctioned write areas outside the session's own working directory derive
# from the current interpreter's home/temp owners and explicit local additions.
# `.claude` is deliberately NOT allowed as a whole: it holds settings.json and
# the guards' own registration, and an agent that can edit the policy enforcing
# its behaviour has no policy. Only the per-project subtree is writable, which
# is where session scratch, workflow scripts and memory live. Skills reach the
# repo through symlinks under `.claude/skills`, and realpath resolves those to
# explicit configured roots, so they stay editable without opening `.claude` itself.


def write_roots():
    _, local = load()
    roots = [os.path.join(os.path.expanduser("~"), ".claude", "projects"), tempfile.gettempdir()]
    if os.name != "nt":
        roots.extend(("/tmp", "/var/tmp"))
    roots.extend(local.get("permissions", {}).get("extra_write_roots", []))
    return [norm(resolve(native(root))) for root in roots]

FILE_TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")


def norm(path):
    """One canonical form for Windows, Git Bash and WSL views of a path.

    C:\\Users\\x -> /c/users/x ; /mnt/c/Users/x -> /c/users/x
    """
    p = path.replace("\\", "/")
    if len(p) > 1 and p[1] == ":":            # C:/x -> /c/x
        p = "/" + p[0] + p[2:]
    if p.startswith("/mnt/") and len(p) > 6 and p[6] == "/":
        p = "/" + p[5] + p[6:]                # /mnt/c/x -> /c/x
    while "//" in p:
        p = p.replace("//", "/")
    p = p.rstrip("/").lower()
    return p or "/"


def under(path, root):
    return path == root or path.startswith(root + "/")


def main():
    data = json.load(sys.stdin)

    tool = data.get("tool_name", "")
    if tool not in FILE_TOOLS:
        return 0

    target = (data.get("tool_input") or {}).get("file_path")
    if not target:
        return 0

    try:
        scratch = write_roots()
    except ConfigError as exc:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": "repo_guard: %s; correct the local configuration before editing" % exc,
        }}))
        return 0

    cwd = data.get("cwd") or os.getcwd()
    # resolve relative targets against the session's working directory
    target = native(target)
    cwd = native(cwd)
    if not os.path.isabs(target) and not (len(target) > 1 and target[1] == ":"):
        target = os.path.join(cwd, target)

    target_n = norm(resolve(target))
    allowed = [norm(resolve(cwd))] + scratch

    for root in allowed:
        if under(target_n, root):
            return 0                          # no decision; normal rules apply

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "repo_guard: %s is outside the working directory (%s) and the "
                "sanctioned scratch areas. Files outside your repos are "
                "read-only. Edit a copy inside the repo, or ask the user to "
                "widen the guard." % (target, cwd)
            ),
        }
    }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:                  # fail open, never wedge a session
        sys.stderr.write("repo_guard: passing through after error: %r\n" % (exc,))
        sys.exit(0)
