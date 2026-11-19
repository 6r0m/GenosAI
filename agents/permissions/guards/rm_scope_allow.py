#!/usr/bin/env python3
"""PermissionRequest hook for Bash: in an unattended session, refuse the prompt.

Claude Code asks a human before some commands even under bypassPermissions -
an rm/rmdir of a critical path, an explicit ask rule, a read outside the
working directories while that block is on. Nobody is there to answer, so the
session would wait. This hook fires at that moment and refuses instead, with a
next step, so the agent reworks the command and keeps going:

    bypassPermissions                     -> DENY; never interrupts the agent
    any other mode, where a user answers  -> no decision ({}): the user decides

It never approves. The payload carries the command, not the reason Claude Code
asked, so an approval could grant a different part of the command than the one
this hook looked at.

The filename is the one both user-level settings.json files register.
Fails open like the other guards: any exception -> {} and the prompt appears.
"""
import json
import os
import sys

sys_path_added = os.path.dirname(os.path.abspath(__file__))
if sys_path_added not in sys.path:
    sys.path.insert(0, sys_path_added)
from _paths import native, next_step, repo_root

# Monitor runs its command under the same permission rules as Bash,
# so it is the same shell surface and gets the same hook.
SHELL_TOOLS = ("Bash", "Monitor")
# Modes in which a prompt would wait for a user who is not there.
UNATTENDED_MODES = ("bypassPermissions",)


def main():
    p = json.load(sys.stdin)
    if p.get("tool_name") not in SHELL_TOOLS:
        return {}
    if p.get("permission_mode") not in UNATTENDED_MODES:
        return {}
    repo = repo_root(native(p.get("cwd") or os.getcwd()))
    return {"hookSpecificOutput": {
        "hookEventName": "PermissionRequest",
        "decision": {"behavior": "deny", "message": (
            "rm_scope_allow: refused automatically - no person was asked. Claude "
            "Code wanted approval for this command, and the session runs "
            "unattended (bypassPermissions). Rework it so it needs no approval: "
            "for a removal, name a literal path inside the repo or its tmp/, or "
            "guard a variable as ${VAR:?}. %s" % next_step(p, repo, "command"))}}}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as exc:               # fail open; the user is asked instead
        sys.stderr.write("rm_scope_allow: passing through after error: %r\n" % (exc,))
        out = {}
    # optional trace for verifying that Claude Code actually invokes this hook
    trace = os.environ.get("RM_SCOPE_TRACE")
    if trace:
        with open(trace, "a") as f:
            f.write(json.dumps({"decision": out}) + "\n")
    print(json.dumps(out))
    sys.exit(0)
