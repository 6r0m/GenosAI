#!/usr/bin/env python3
"""Assert that a settings file registers every guard on the right event.

    python3 check-registration.py <settings.json> [...]

Counting occurrences of `run-guard.sh` is not enough. Three references to the
same guard, a guard bound to the wrong event or matcher, or three matches in an
unrelated part of the file all satisfy a count while leaving a guard that never
runs - the same silent failure the interpreter stub produced. So this parses the
file and checks each expected (event, matcher, guard) triple individually.

A missing settings file is a failure, not a skip: "the file I was going to check
isn't there" is precisely when a guard is silently absent.

Exit 0 when every expectation holds, 1 otherwise; findings go to stdout.
"""
import json
import os
import sys

# (hook event, matcher as written in settings, guard filename)
# Monitor runs commands under Bash's permission rules, so a Bash-only matcher
# lets `Monitor(command="rm -rf ...")` past the guard entirely.
EXPECTED = [
    ("PreToolUse", "Bash|Monitor", "bash_rm_guard.py"),
    ("PreToolUse", "Edit|Write|NotebookEdit", "repo_guard.py"),
    ("PermissionRequest", "Bash|Monitor", "rm_scope_allow.py"),
]


def commands(settings, event, matcher):
    out = []
    for group in settings.get("hooks", {}).get(event, []):
        if group.get("matcher") != matcher:
            continue
        for hook in group.get("hooks", []):
            out.append(hook.get("command", ""))
    return out


def check(path):
    if not os.path.isfile(path):
        return ["missing settings file: %s" % path]
    try:
        with open(path, encoding="utf-8") as fh:
            settings = json.load(fh)
    except ValueError as exc:
        return ["%s: not valid JSON: %s" % (path, exc)]
    return check_settings(settings, path)


def check_settings(settings, path):
    problems = []
    problems.extend(powershell_posture(path, settings))
    problems.extend(monitor_posture(path, settings))

    for event, matcher, guard in EXPECTED:
        found = [c for c in commands(settings, event, matcher) if guard in c]
        if not found:
            problems.append("%s: %s on %s[%s] is not registered"
                            % (path, guard, event, matcher))
            continue
        for command in found:
            if "run-guard.sh" not in command:
                problems.append(
                    "%s: %s runs without run-guard.sh, so a missing guard would "
                    "exit 2 and block every tool call" % (path, guard))

    # Any guard invoked directly is the wedge this indirection exists to prevent.
    for event in ("PreToolUse", "PermissionRequest", "PostToolUse"):
        for group in settings.get("hooks", {}).get(event, []):
            for hook in group.get("hooks", []):
                command = hook.get("command", "")
                if "guards/" in command and "run-guard.sh" not in command:
                    problems.append("%s: %s[%s] invokes a guard directly: %s"
                                    % (path, event, group.get("matcher"),
                                       command[:60]))
    return problems


def powershell_posture(path, settings):
    """The PowerShell tool must be shut off, or it is an unguarded shell.

    On Windows with Git Bash installed it is enabled by default for claude.ai
    and Console accounts, it carries its own `tool_input.command`, and the
    guards match `Bash` only - so `Remove-Item -Recurse -Force` would bypass
    every check here. Rather than maintain a second destructive-command parser
    for a tool this setup does not use, it is disabled twice over: the env var
    stops it being offered, and the deny rule blocks it even if the env is
    wrong or overridden elsewhere. PowerShell stays reachable through Bash.
    """
    problems = []
    env = settings.get("env", {})
    if str(env.get("CLAUDE_CODE_USE_POWERSHELL_TOOL", "")) != "0":
        problems.append("%s: env.CLAUDE_CODE_USE_POWERSHELL_TOOL is not \"0\"; "
                        "the PowerShell tool bypasses every Bash guard" % path)
    if not powershell_denied(settings.get("permissions", {}).get("deny", [])):
        problems.append("%s: no whole-tool PowerShell deny; a narrow rule such "
                        "as PowerShell(Get-ChildItem *) is not a backstop" % path)
    return problems


def powershell_denied(deny):
    """Only a whole-tool deny counts.

    `PowerShell(Remove-Item *)` blocks one command; every other PowerShell
    command still runs unguarded. Accepting any `PowerShell(...)` rule as proof
    of a backstop would let a narrow, unrelated rule satisfy the check.
    """
    return "PowerShell" in deny or "PowerShell(*)" in deny


def monitor_posture(path, settings):
    if settings.get('permissions',{}).get('defaultMode') in ('default','acceptEdits','plan','dontAsk'):
        return []
    """Monitor must be allowed as a whole tool, or its watch loops stall.

    A bare `Bash` allow does not carry over: outside bypass and auto mode, a
    Monitor command with a `$` expansion asks ("Contains simple_expansion")
    while Bash runs the same command. Deny rules and the PreToolUse guard still
    win over this allow; auto mode sets it aside and the classifier decides.
    """
    allow = settings.get("permissions", {}).get("allow", [])
    if "Monitor" in allow or "Monitor(*)" in allow:
        return []
    return ["%s: no whole-tool Monitor allow; watch commands with a $ expansion "
            "prompt in Manual, acceptEdits and plan modes" % path]


def main(argv):
    if not argv:
        print("usage: check-registration.py <settings.json> [...]")
        return 1
    problems = []
    for path in argv:
        problems.extend(check(path))
    for line in problems:
        print("  *** " + line)
    if not problems:
        print("  %d settings file(s): all %d guard registrations correct"
              % (len(argv), len(EXPECTED)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
