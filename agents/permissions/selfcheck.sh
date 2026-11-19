#!/usr/bin/env bash
# Do the permission guards actually work on THIS platform?
#
#   bash agents/permissions/selfcheck.sh
#
# Run it under WSL and again under Git Bash on Windows. It drives run-guard.sh,
# the same launcher settings.json uses, so it fails where the real hook would.
# That matters because the guards fail OPEN: from inside a session a guard that
# never ran is indistinguishable from one that allowed the command. On Windows
# this check is the only thing that catches it - `python3` there resolves to the
# Microsoft Store alias, which exits 49 without running anything.
#
# Only nonexistent paths are passed, and a guard only answers allow/deny; it
# never executes the command it is asked about. Nothing is deleted.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/../lifecycle/platform-paths.sh"
RUNNER="$HERE/run-guard.sh"
fail=0

echo "platform : ${OSTYPE-unknown}"
echo "guards   : $HERE/guards"

if [ ! -f "$RUNNER" ]; then
    echo "  *** run-guard.sh missing at $RUNNER ***"
    exit 1
fi

for candidate in "python3" "python" "py -3" "python3.exe" "python.exe"; do
    if $candidate -c "import sys; sys.exit(0)" >/dev/null 2>&1; then
        echo "  python : $candidate (executed, not just found)"
        PY_CMD="$candidate"
        found=1
        break
    fi
done
if [ -z "${found-}" ]; then
    echo "  python : *** none of the candidates actually runs ***"
    exit 1
fi

probe() {                                   # probe <command> <deny|allow>
    printf '  %-36s -> ' "$1"
    got=allow
    printf '{"tool_name":"Bash","cwd":"/","tool_input":{"command":"%s"}}' "$1" \
        | bash "$RUNNER" bash_rm_guard.py 2>/dev/null | grep -q bash_rm_guard && got=deny
    if [ "$got" = "$2" ]; then
        echo "$got (correct)"
    else
        echo "*** $got, expected $2 ***"
        fail=1
    fi
}

probe "rm -rf /etc/nonexistent-probe"        deny
probe "/bin/rm -rf /etc/nonexistent-probe"   deny
probe "rm -rf /"                             deny
probe "rm -rf \$HOME"                        deny
probe "rm -rf /tmp/nonexistent-probe"        allow
probe "rm /etc/nonexistent-probe"            allow
probe "rm -rf /tmp/*"                        deny

# The unit suite drives the guard with a synthetic cwd. This probe uses the
# shell's real $PWD instead, in its native spelling - /e/... under Git Bash,
# /mnt/e/... under WSL - which is exactly what Claude Code sends. A relative
# in-repo delete was refused on Windows because that spelling was never
# normalised, and only paths whose text contained a temp-named component
# escaped it, so a `tmp/...` probe would have looked fine.
relprobe() {                                # relprobe <relative path> <deny|allow>
    printf '  %-36s -> ' "cwd-relative $1"
    got=allow
    printf '{"tool_name":"Bash","cwd":"%s","tool_input":{"command":"rm -rf %s"}}' \
        "$PWD" "$1" \
        | bash "$RUNNER" bash_rm_guard.py 2>/dev/null | grep -q bash_rm_guard && got=deny
    if [ "$got" = "$2" ]; then
        echo "$got (correct)"
    else
        echo "*** $got, expected $2 ***"
        fail=1
    fi
}

echo "  -- real cwd spelling --"
relprobe "src/nonexistent-probe"  allow
relprobe "tmp/nonexistent-probe"  allow
relprobe "../nonexistent-probe"   deny

# The PermissionRequest answer. Under bypassPermissions nobody is there to
# answer a prompt, so every prompt must come back refused; in a mode where the
# user answers, it must be left alone. It never approves anything.
askprobe() {                                # askprobe <mode> <command> <allow|deny|none>
    printf '  %-36s -> ' "$1: $2"
    out=$(printf '{"tool_name":"Bash","permission_mode":"%s","cwd":"%s","tool_input":{"command":"%s"}}' \
        "$1" "$PWD" "$2" | bash "$RUNNER" rm_scope_allow.py 2>/dev/null)
    got=none
    case "$out" in
        *'"behavior": "allow"'*) got=allow ;;
        *'"behavior": "deny"'*) got=deny ;;
    esac
    if [ "$got" = "$3" ]; then
        echo "$got (correct)"
    else
        echo "*** $got, expected $3 ***"
        fail=1
    fi
}

echo "  -- rm_scope_allow (prompts) --"
askprobe bypassPermissions 'rm -f /nonexistent-probe'         deny
askprobe bypassPermissions 'rm -rf tmp/nonexistent-probe'     deny
askprobe default           'rm -rf tmp/nonexistent-probe'     none

fileprobe() {                               # fileprobe <path> <deny|allow>
    printf '  %-36s -> ' "$(echo "$1" | sed "s|$HOME|~|")"
    got=allow
    printf '{"tool_name":"Edit","cwd":"%s","tool_input":{"file_path":"%s"}}' \
        "$PWD" "$1" \
        | bash "$RUNNER" repo_guard.py 2>/dev/null | grep -q permissionDecision && got=deny
    if [ "$got" = "$2" ]; then
        echo "$got (correct)"
    else
        echo "*** $got, expected $2 ***"
        fail=1
    fi
}

echo "  -- repo_guard (file edits) --"
fileprobe "$PWD/nonexistent-file-probe"            allow
fileprobe "$HOME/.claude/projects/p/memory/n.md"    allow
fileprobe "$HOME/.claude/settings.json"             deny
fileprobe "/etc/passwd"                             deny

# The guards are only real if settings actually register them. A guard that is
# correct but unregistered passes every probe above and does nothing in a live
# session - the same silent failure the interpreter stub produced. Counting
# `run-guard.sh` occurrences would not catch a guard bound to the wrong event,
# so check-registration.py asserts each (event, matcher, guard) triple, and
# treats a missing settings file as a failure rather than a skip.
echo "  -- settings registration --"
CFGS=("${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json")
case "${OSTYPE-}" in
    linux*)
        if command -v cmd.exe >/dev/null 2>&1; then
            if profile=$(windows_profile) && win_home=$(wslpath -u "$profile") && [[ -n "$win_home" ]]; then
                CFGS+=("$win_home/.claude/settings.json")
            else
                echo "  *** cannot discover the Windows settings path ***"
                fail=1
            fi
        fi ;;
esac
$PY_CMD "$HERE/check-registration.py" "${CFGS[@]}" || fail=1

# The same files against the tracked Claude settings; a difference is drift to review and install.
echo "  -- Claude settings (tracked file vs live) --"
SIDES=()
for ((i = 0; i < ${#CFGS[@]}; i++)); do
    side=wsl
    case "${OSTYPE-}" in msys*|cygwin*|win32*) side=windows ;; esac
    [[ "$i" == 0 ]] || side=windows
    SIDES+=(--side "$side" "${CFGS[i]}")
done
$PY_CMD "$HERE/../providers/claude/settings.py" check "${SIDES[@]}" || fail=1

# The session-start drift warning as Claude Code runs it: the command this side registers, run and judged
# by its owner. Clean means exit 0, no output, within its timeout; anything else, or no registration, fails.
printf '  %-36s -> ' "session-start drift warning"
$PY_CMD "$HERE/../providers/claude/settings.py" registered-hook --settings "${CFGS[0]}" || fail=1

# A guard that cannot be found must degrade to "no decision", never to exit 2 -
# exit 2 is PreToolUse's blocking convention and would brick every session on
# this machine, in every repository, not just this one.
printf '  %-36s -> ' "missing guard degrades safely"
out=$(bash "$RUNNER" no_such_guard.py </dev/null 2>/dev/null); rc=$?
if [ "$rc" -eq 0 ] && [ "$out" = "{}" ]; then
    echo "exit 0, {} (correct)"
else
    echo "*** exit $rc, stdout [$out] ***"
    fail=1
fi

# Everything above proves the scripts. Whether the installed Claude Code still
# calls them is live-check.sh's to prove, and VS Code updates the extension
# without telling anyone - so report whether the installed builds were checked.
# Reported, not failed: an unchecked build is unproven, not broken.
echo "  -- live-check of the installed Claude Code builds --"
case "${OSTYPE-}" in
    linux*) bash "$HERE/live-check.sh" --status ;;
    *) echo "  (shown when selfcheck.sh runs under WSL)" ;;
esac

echo "  -- Pi permission gate --"
pi_probe=$($PY_CMD -c "import json,os; print(json.dumps({'cwd': os.getcwd()}))" | bash "$RUNNER" ../../providers/pi/permissions/gate.py --probe "$PWD")
printf '%s' "$pi_probe" | $PY_CMD -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('pi_gate') == 1 and d.get('healthy') is True and all(c.get('allow') is False for c in d.get('cases', [])) else 1)" || fail=1

if [ "$fail" -eq 0 ]; then
    echo "OK - guards behave correctly on this platform"
else
    echo "FAILED - see the lines marked *** above"
fi
exit "$fail"
