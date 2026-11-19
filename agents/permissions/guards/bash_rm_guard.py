#!/usr/bin/env python3
"""PreToolUse guard for Bash: block a *recursive* delete whose target is not
provably inside the working repo or below a temp-named directory through a
named child of it (`/tmp/job/x` is one job's area; `/tmp/*` is every job's).

Why PreToolUse and not PermissionRequest
----------------------------------------
The earlier `rm_scope_allow.py` did the same analysis on the PermissionRequest
event and answered "allow". That event only fires when Claude Code is about to
raise a permission prompt. Under `defaultMode: bypassPermissions` a deny rule
blocks the call outright and no prompt is ever raised, so the allowlist never
ran: `Bash(rm -rf /*)` blocked every recursive delete and nothing could rescue
the safe ones. Agents then reached for `shutil.rmtree` or `/bin/rm`, which the
string-matching deny rule does not see at all.

Inverting it fixes that. This hook runs before every Bash call, in every mode,
and *denies* what it can prove is out of scope instead of *allowing* what it
can prove is in scope. `Bash(rm -rf /*)` is dropped from settings.json so this
hook is the single owner of rm scope; the narrow literal denies (`rm -rf /`,
`rm -rf ~`, `rm -rf $HOME*`, the `.git` ones) stay as a cheap backstop.

What this guard does not do: predict which commands Claude Code will itself
stop for a human (a critical-path removal, an ask rule). Those prompts reach
rm_scope_allow.py on PermissionRequest, which refuses them in an unattended
session, so the parser that decides stays Claude Code's own.

Decision table
--------------
    recursive rm, every target inside repo or below a temp dir  -> defer ({})
    recursive rm, any target provably outside                   -> DENY
    recursive rm, a target that cannot be resolved ($VAR, ~, ``) -> DENY
    non-recursive rm, rmdir, anything else                      -> defer ({})
    unparseable command, or any exception in this script        -> defer ({})

An unresolvable target is denied rather than deferred: a recursive delete whose
destination this script cannot determine is exactly the case the guard exists
for, and a gate handed an unknown fails closed. A *crash* is different and
fails open - a bug here must never wedge a session, matching the choice already
documented in repo_guard.py.

Note this is a guard against accidents, not a security boundary: an agent that
means to delete can still call Python. Real boundaries need OS-level controls.

SOT: agents/permissions/guards/. Registered for
both WSL and Windows in the PreToolUse.Bash hook, which resolves the repo path
per platform and launches this guard through ../run-guard.sh.
"""
import json
import os
import re
import shlex
import sys

sys_path_added = os.path.dirname(os.path.abspath(__file__))
if sys_path_added not in sys.path:
    sys.path.insert(0, sys_path_added)
from _paths import native, next_step, repo_root, resolve

TEMP_DIR_RE = re.compile(
    r"^\.?(tmp|temp|temporary|scratch|scratchpad)([._-]\w*)?$", re.IGNORECASE)
GLOB_RE = re.compile(r"[*?\[]")
REDIRECT_OP_RE = re.compile(r"^\d*[<>]{1,2}&?\d*$")
REDIRECT_TOK_RE = re.compile(r"^(\d*[<>]{1,2}&?\S+|&>\S*)$")
# -r, -R, --recursive, and combined short flags such as -rf / -fr / -Rv
RECURSIVE_RE = re.compile(r"^(--recursive|-[A-Za-z]*[rR][A-Za-z]*)$")

# Monitor runs its command under the same permission rules as Bash,
# so it is the same shell surface and gets the same guard.
SHELL_TOOLS = ("Bash", "Monitor")

UNRESOLVED = object()


def main():
    payload = json.load(sys.stdin)
    if payload.get("tool_name") not in SHELL_TOOLS:
        return {}
    cmd = (payload.get("tool_input") or {}).get("command", "")
    # native() here, not just on repo/target: every relative target is joined
    # against this cwd, and a Git Bash /e/... spelling would drag the join onto
    # the wrong drive. Only a relative path whose text happens to contain a
    # temp-named component escaped that, which is why it looked fine.
    cwd = native(payload.get("cwd") or os.getcwd())
    repo = repo_root(cwd)

    if not re.search(r"\brm\b", cmd):
        return {}

    env, offenders = {}, []
    for seg in split_segments(cmd):
        try:
            toks = shlex.split(seg)
        except ValueError:
            return {}                      # unparseable -> defer
        while toks and re.fullmatch(r"[A-Za-z_]\w*=.*", toks[0], re.S):
            key, val = toks[0].split("=", 1)
            env[key] = val
            toks = toks[1:]
        toks = strip_wrappers(toks)
        if not toks:
            continue
        if toks[0] == "cd":
            if len(toks) < 2 or toks[1].startswith("-"):
                return {}                  # unknown cwd from here on -> defer
            moved = expand(toks[1], env)
            if moved is UNRESOLVED:
                return {}
            cwd = os.path.normpath(os.path.join(cwd, native(moved)))
            continue
        if os.path.basename(toks[0]) != "rm":
            continue
        flags = [t for t in toks[1:] if t.startswith("-") and t != "--"]
        if not any(RECURSIVE_RE.match(f) for f in flags):
            continue                       # non-recursive rm is not our business
        for raw in rm_targets(toks[1:]):
            resolved = expand(raw, env)
            if resolved is UNRESOLVED:
                offenders.append("%s (unresolved)" % raw)
                continue
            # native() before the join: os.path.join("C:/x", "/c/y") yields
            # "C:/c/y" on Windows, so a Git Bash drive path must be spelled
            # natively while it is still a standalone absolute path.
            target = resolve(os.path.normpath(os.path.join(cwd, native(resolved))))
            # A temp-named ancestor must not override working-tree protection.
            target_key = os.path.normcase(target).replace("\\", "/").rstrip("/")
            repo_key = os.path.normcase(repo).replace("\\", "/").rstrip("/") if repo else None
            protected = repo_key is not None and (
                repo_key == target_key or repo_key.startswith(target_key + "/") or
                target_key == repo_key + "/.git" or target_key.startswith(repo_key + "/.git/"))
            if protected or not (inside_repo(target, repo) or below_temp_dir(target)):
                offenders.append(target)

    if not offenders:
        return {}
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            "bash_rm_guard: recursive delete outside the allowed scope: %s. "
            "Recursive deletes are permitted only strictly inside the working "
            "repo (%s) or below a temp-named directory through a named child "
            "of it. %s" % (", ".join(offenders),
                           repo or "no working repo: this session started in a "
                                   "home folder or at a drive root",
                           next_step(payload, repo, "removal")))}}


def strip_wrappers(toks):
    """Drop the wrappers Claude Code itself strips before rule matching."""
    wrappers = ("timeout", "time", "nice", "nohup", "stdbuf", "command",
                "builtin", "noglob", "xargs")
    while toks and os.path.basename(toks[0]) in wrappers:
        toks = toks[1:]
        while toks and toks[0].startswith("-"):
            toks = toks[1:]
        # `timeout 900 cmd` - drop a bare numeric/duration argument
        if toks and re.fullmatch(r"\d+[smhd]?", toks[0]):
            toks = toks[1:]
    return toks


def split_segments(cmd):
    """Split on ; && || | & and newlines, but not inside quotes/backticks/$()."""
    segs, cur, i, n, quote, depth = [], [], 0, len(cmd), None, 0
    while i < n:
        c = cmd[i]
        if quote:
            cur.append(c)
            if c == "\\" and quote == '"' and i + 1 < n:
                cur.append(cmd[i + 1]); i += 2; continue
            if c == quote:
                quote = None
            i += 1; continue
        if c in "'\"`":
            quote = c; cur.append(c); i += 1; continue
        if c == "\\" and i + 1 < n:
            cur.append(c); cur.append(cmd[i + 1]); i += 2; continue
        if cmd.startswith("$(", i):
            depth += 1; cur.append("$("); i += 2; continue
        if depth:
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            cur.append(c); i += 1; continue
        sep = None
        for op in ("&&", "||", ";", "|", "\n"):
            if cmd.startswith(op, i):
                sep = op; break
        if sep is None and c == "&":
            prev = cmd[i - 1] if i else ""
            nxt = cmd[i + 1] if i + 1 < n else ""
            if prev not in "<>" and nxt not in "<>":
                sep = "&"
        if sep:
            segs.append("".join(cur)); cur = []; i += len(sep); continue
        cur.append(c); i += 1
    segs.append("".join(cur))
    return segs


def rm_targets(toks):
    args, dashdash, i = [], False, 0
    while i < len(toks):
        t = toks[i]
        if REDIRECT_OP_RE.match(t):
            i += 2; continue
        if REDIRECT_TOK_RE.match(t):
            i += 1; continue
        if dashdash or not t.startswith("-"):
            args.append(t)
        elif t == "--":
            dashdash = True
        i += 1
    return args


def expand(s, env):
    """Resolve a leading $VAR from the command's own assignments, else UNRESOLVED."""
    m = re.match(r"^\$(?:\{(\w+)\}|(\w+))(.*)$", s)
    if not m:
        if "$" in s or s.startswith("~") or "`" in s:
            return UNRESOLVED
        return s
    name = m.group(1) or m.group(2)
    if not env.get(name):
        return UNRESOLVED
    return env[name] + m.group(3)


def inside_repo(target, repo):
    """Strictly inside: the repo root itself is never a legal delete target."""
    if repo is None:
        return False                       # the session's folder is no repo
    if not target.startswith(repo + os.sep) and not target.startswith(repo + "/"):
        return False
    first = target[len(repo) + 1:].replace("\\", "/").split("/", 1)[0]
    return bool(first) and first != ".." and not GLOB_RE.search(first)


def below_temp_dir(target):
    """Below a temp-named component, through a literal child of it.

    Never the temp root itself, and never a glob directly under it: `/tmp/*`
    sits below `tmp` only lexically, and names every session's scratch.
    """
    parts = [x for x in target.replace("\\", "/").split("/") if x]
    return any(TEMP_DIR_RE.match(c) and i < len(parts) - 1
               and not GLOB_RE.search(parts[i + 1])
               and ".." not in parts[i + 1:]
               for i, c in enumerate(parts))


if __name__ == "__main__":
    try:
        print(json.dumps(main()))
    except Exception as exc:               # fail open; never wedge a session
        sys.stderr.write("bash_rm_guard: passing through after error: %r\n" % (exc,))
        print("{}")
    sys.exit(0)
