#!/usr/bin/env bash
# SessionStart adapter for the Claude settings drift warning.
#
# Claude Code can add a SessionStart hook's plain stdout to the model's context, so this prints nothing
# for a clean side and only the JSON systemMessage otherwise. run-guard.sh stays the one owner of
# interpreter choice; when it cannot launch anything it prints `{}` and exits 0, which is right for a
# guard and wrong for a warning. So only the hook mode's positive answers pass: `clean`, or a
# systemMessage object. Anything else exits 1, and the registered command's `|| printf` turns that into
# a "could not run" warning.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="$(bash "$HERE/../../permissions/run-guard.sh" ../../providers/claude/settings.py hook </dev/null)" || exit 1
# Windows Python ends its lines with CRLF.
out="${out//$'\r'/}"
case "$out" in
    clean) exit 0 ;;
    '{"systemMessage":'*) printf '%s\n' "$out"; exit 0 ;;
esac
exit 1
