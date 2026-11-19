#!/usr/bin/env bash
# Launch one guard from guards/ under a Python that actually runs.
#
#   bash run-guard.sh <guard-file.py>     # hook JSON on stdin, decision on stdout
#
# Why interpreters are executed, not looked up
# --------------------------------------------
# The hook command used to pick its interpreter with `command -v python3`. On
# Windows that resolves to %LOCALAPPDATA%\Microsoft\WindowsApps\python3, the
# Microsoft Store alias: it exists, so the lookup succeeds, but running it
# prints "Python was not found" and exits 49. The guard produced no stdout,
# Claude Code read no decision, and every recursive delete was allowed. Because
# the guards fail open by design this was indistinguishable from a healthy
# session - the Windows side ran unguarded until selfcheck.sh was pointed at it.
# Presence is not capability, so a candidate is chosen by executing it.
#
# Why this file exists at all
# ---------------------------
# It is the single owner of interpreter resolution, which is the fragile part.
# The hook command in settings.json only resolves the repo path per platform and
# delegates here, so that logic is written once and covered by
# tests/test_bash_rm_guard.py::InterpreterResolution.
#
# It also bounds the blast radius of a missing guard. Invoking `python3 <path>`
# directly exits 2 when the file is absent, and exit 2 is PreToolUse's blocking
# convention - renaming a guard bricked every Bash and Write call in the session
# until the old path was restored. Here stdout is always valid JSON and the exit
# status is always 0, so an absent or unrunnable guard degrades to "no decision"
# rather than wedging the session.
#
# Be clear about what that costs: for recursive deletes there is no meaningful
# backstop underneath. The deny rules cover literal `rm -rf /`, `~` and `$HOME`
# and nothing else - `Bash(bash)` and `Bash(sh)` are exact-match and do not
# cover `bash -c`, and no rule covers `/bin/rm -rf /etc`. If no Python runs on
# a machine, that whole class of command is unguarded there. selfcheck.sh is
# what surfaces it.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="${1-}"

if [ -z "$GUARD" ] || [ ! -f "$HERE/guards/$GUARD" ]; then
    echo "run-guard: no such guard: ${GUARD:-<none>}" >&2
    printf '{}\n'
    exit 0
fi
shift

# `py -3` is a candidate because the Windows launcher is present on machines
# where every bare name is a Store alias. Unquoted expansion is deliberate: the
# candidate carries its own argument.
launch_error="no working Python 3 found"
for candidate in "python3" "python" "py -3" "python3.exe" "python.exe"; do
    if runtime=$($candidate -c "import os,sys; sys.exit(1) if sys.version_info[0] < 3 else None; print(os.name)" 2>/dev/null); then
        runtime="${runtime//$'\r'/}"
        script="$HERE/guards/$GUARD"
        case "$runtime" in
            nt)
                # Native Python cannot read a Git Bash /e/... spelling. MSYS
                # conversion can skip paths containing shell metacharacters.
                launch_error="cannot resolve the native Python script path"
                if command -v cygpath >/dev/null 2>&1; then
                    script=$(cygpath -m -- "$script") || break
                elif command -v wslpath >/dev/null 2>&1; then
                    script=$(wslpath -w "$script") || break
                else
                    break
                fi
                [[ -n "$script" ]] || break ;;
            posix) ;;
            *) continue ;;
        esac
        exec $candidate "$script" "$@"
    fi
done

echo "run-guard: $launch_error; $GUARD did not run" >&2
printf '{}\n'
exit 0
