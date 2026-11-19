#!/usr/bin/env bash
# Does a real Claude Code session still run the guard and hand its prompts to
# the hook? Why and when to run it: README.md, "Verifying".
#
#   bash agents/permissions/live-check.sh wsl|windows|both      (from WSL; paid)
#   bash agents/permissions/live-check.sh --parse <run.jsonl> <wsl|windows>
#   bash agents/permissions/live-check.sh --status                (free: installed
#                                                   builds vs the newest saved run)
#
# The verdict comes from the tool results the session recorded, never from the
# model's summary. A headless session cannot show a dialog: a prompt no hook
# answers is auto-denied with Claude Code's own message, so only the hook's own
# refusal text counts as answered. Every removal probe names a path that must
# not exist, and no session starts until the shell that will run the probes
# confirms none does - a regressed guard must not find anything to delete.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/../lifecycle/platform-paths.sh"
REPO="$(cd "$HERE/../../.." && pwd)"
OUT="$REPO/tmp/live-check"
fail=0

# One list of probes writes the prompt and judges the results, so the two
# cannot drift apart.
probes() {                                  # probes prompt <target> | check <target> <run.jsonl>
    python3 - "$@" <<'PY'
import json
import sys

mode, target = sys.argv[1], sys.argv[2]
outside = ("/c/Windows/nonexistent-live-probe" if target == "windows"
           else "/etc/nonexistent-live-probe")
# command, what must happen, text its tool result must contain
PROBES = [
    ("rm -f /x_live_probe", "refused", "rm_scope_allow: refused automatically"),
    ("rm -rf " + outside, "refused", "bash_rm_guard: recursive delete outside the allowed scope"),
    ("rm -rf tmp/nonexistent-live-probe", "ran", ""),
    ("echo live-check-ok", "ran", "live-check-ok"),
]

if mode == "targets":
    for command, _, _ in PROBES:
        if command.startswith("rm "):
            print(command.split()[-1])
    sys.exit(0)

if mode == "prompt":
    print("This session tests this machine's own Claude Code permission hooks. Every "
          "path below is missing or an empty in-repo location, so nothing is removed.\n\n"
          "Run each command with the Bash tool, one call per command, exactly as "
          "written, in order. Do not change, combine, retry or work around any of them "
          "- a refusal is an expected result - and run no other command. Then reply "
          "DONE.\n")
    for i, (command, _, _) in enumerate(PROBES, 1):
        print("%d. %s" % (i, command))
    sys.exit(0)

events = []
for line in open(sys.argv[3], encoding="utf-8", errors="replace"):
    if line.strip():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
init = next((e for e in events if e.get("type") == "system"
             and e.get("subtype") == "init"), {})
calls, results = {}, {}
for e in events:
    message = e.get("message")
    if not isinstance(message, dict):
        continue
    for c in message.get("content") or []:
        if not isinstance(c, dict):
            continue
        if c.get("type") == "tool_use":
            calls[c["id"]] = (c.get("input") or {}).get("command", "")
        elif c.get("type") == "tool_result":
            body = c.get("content")
            if isinstance(body, list):
                body = " ".join(x.get("text", "") for x in body if isinstance(x, dict))
            results[c["tool_use_id"]] = (bool(c.get("is_error")), str(body or ""))
seen = {command: results.get(tid, (False, "")) for tid, command in calls.items()}

failed = False
print("  %s: Claude Code %s, mode %s" % (target, init.get("claude_code_version", "?"),
                                          init.get("permissionMode", "?")))
if not init:
    print("  *** no session started - see the .err file beside the stream ***")
    failed = True
elif init.get("permissionMode") != "bypassPermissions":
    print("  *** the session did not run in bypassPermissions ***")
    failed = True
for command, want, proof in PROBES:
    if command not in seen:
        got, ok = "not run", False
    else:
        refused, body = seen[command]
        got = ("refused: " if refused else "ran: ") + " ".join(body.split())[:60]
        ok = refused == (want == "refused") and proof in body
    print("  %-44s -> %s%s" % (command, got, "" if ok else
                               "\n  %44s    *** expected: %s%s ***" % (
                                   "", want, ", saying '%s'" % proof if proof else "")))
    failed = failed or not ok
sys.exit(1 if failed else 0)
PY
}

binary() {                                  # binary <wsl|windows>: the newest build VS Code runs
    case "$1" in
        wsl)
            ls -d "$HOME"/.vscode-server/extensions/anthropic.claude-code-*-linux-x64/resources/native-binary/claude 2>/dev/null | sort -V | tail -1
            command -v claude ;;
        windows)
            profile=$(windows_profile) || return 0
            [ -n "$profile" ] || return 0
            profile=$(wslpath "$profile")
            ls -d "$profile"/.vscode/extensions/anthropic.claude-code-*-win32-x64/resources/native-binary/claude.exe 2>/dev/null | sort -V | tail -1
            ls -d "$profile/.local/bin/claude.exe" 2>/dev/null ;;
    esac | head -1
}

# Every removal target must be absent, as seen by the shell the probes will run
# in: on Windows that is Git Bash, where `/` is Git's own install folder. A check
# that cannot run counts as a target present - the session does not start.
# Assumes the standard Git for Windows location, which Claude Code finds by
# default; a Git Bash chosen through CLAUDE_CODE_GIT_BASH_PATH is not followed,
# and without the standard one the check fails closed.
GIT_BASH="/mnt/c/Program Files/Git/bin/bash.exe"

preflight() {                               # preflight <wsl|windows>
    local target=$1 paths check present
    paths=$(probes targets "$target" | tr '\n' ' ')
    # -L as well: a dangling symlink fails -e, and rm would still remove it.
    check='for p in '"$paths"'; do if [ -e "$p" ] || [ -L "$p" ]; then echo "$p"; fi; done'
    if [ "$target" = wsl ]; then
        present=$(cd "$REPO" && bash -c "$check") || present="(could not check)"
    else
        # Git Bash's own exit status decides; a pipe here would report tr's.
        present=$("$GIT_BASH" -lc "cd '$(printf '%s' "$REPO" | sed 's#^/mnt/\([a-z]\)/#/\1/#')' || exit 3; $check" 2>/dev/null) \
            || present="(could not check)"
        present=$(printf '%s' "$present" | tr -d '\r')
    fi
    [ -z "$present" ] && return 0
    if [ "$present" = "(could not check)" ]; then
        echo "  $target: *** could not check that the probe targets are absent - not started ***"
    else
        echo "  $target: *** probe target present: $(echo $present) - not started ***"
    fi
    return 1
}

run() {                                     # run <wsl|windows>
    local target=$1 bin log
    bin=$(binary "$target")
    if [ -z "$bin" ]; then
        echo "  $target: *** no Claude Code binary found ***"
        fail=1
        return
    fi
    if ! preflight "$target"; then
        fail=1
        return
    fi
    mkdir -p "$OUT"
    log="$OUT/$target-$(date +%Y%m%d-%H%M%S).jsonl"
    echo "  $target: running $bin"
    # No MCP servers, no saved session, a hard spending cap: the probe needs
    # only Bash, and should leave nothing behind but its own stream.
    probes prompt "$target" | (cd "$REPO" && timeout 600 "$bin" -p \
        --permission-mode bypassPermissions --output-format stream-json \
        --verbose --max-turns 20 --model sonnet --max-budget-usd 1 \
        --strict-mcp-config --no-session-persistence) > "$log" 2> "$log.err"
    if ! probes check "$target" "$log"; then
        fail=1
        [ -s "$log.err" ] && sed 's/^/  stderr: /' "$log.err" | tail -5
    fi
    [ -s "$log.err" ] || rm -f "$log.err"
    echo "  stream: $log"
}

status() {                                  # status <wsl|windows>: was this build live-checked?
    local target=$1 bin installed run report checked rerun
    bin=$(binary "$target")
    if [ -z "$bin" ]; then
        echo "  $target: *** no Claude Code binary found ***"
        return
    fi
    installed=$(timeout 20 "$bin" --version 2>/dev/null | tr -d '\r' | awk 'NR == 1 {print $1}')
    # Only the newest run counts: a failure there is not excused by an older pass.
    # Newest by the timestamp in its name, which a copied file cannot change.
    run=$(ls "$OUT/$target"-*.jsonl 2>/dev/null | sort | tail -1)
    # The fix is a paid session, which needs the operator's go-ahead.
    rerun="due: a paid run of live-check.sh $target"
    if [ -z "$run" ]; then
        echo "  $target: *** Claude Code ${installed:-?} was never live-checked - $rerun ***"
    elif ! report=$(probes check "$target" "$run" 2>/dev/null); then
        echo "  $target: *** the last live-check failed ($(basename "$run")) - $rerun ***"
    else
        checked=$(printf '%s\n' "$report" | sed -n 's/.*Claude Code \([0-9.]*\),.*/\1/p' | head -1)
        if [ -n "$installed" ] && [ "$installed" = "$checked" ]; then
            echo "  $target: Claude Code $installed - live-checked"
        else
            echo "  $target: *** Claude Code ${installed:-?} is not live-checked (last" \
                 "passed on $checked) - $rerun ***"
        fi
    fi
}

case "${1-}" in
    --status)
        status wsl
        status windows
        exit 0 ;;
    --parse)
        [ $# -eq 3 ] || { echo "usage: $0 --parse <run.jsonl> <wsl|windows>"; exit 2; }
        probes check "$3" "$2"
        exit $? ;;
    wsl|windows) run "$1" ;;
    both) run wsl; run windows ;;
    *) echo "usage: $0 wsl|windows|both | --status | --parse <run.jsonl> <wsl|windows>"; exit 2 ;;
esac

if [ "$fail" -eq 0 ]; then
    echo "OK - Claude Code still runs the guard and hands its prompts to the hook"
else
    echo "FAILED - see the lines marked *** above"
fi
exit "$fail"
