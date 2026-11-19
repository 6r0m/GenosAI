#!/usr/bin/env bash
# Regenerates the derived Pi install lock from the lifecycle pin. The operator edits only PI_PACKAGE;
# this script derives install-lock/package.json and lets npm pin the full dependency tree.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
AI_ROOT="$(cd -- "$HERE/../../../.." && pwd -P)"
source "$AI_ROOT/lifecycle/registry.sh"
load_registry
[[ "${PI_PACKAGE-}" =~ ^(@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*@[0-9][0-9A-Za-z.+-]*$ ]] || { echo 'error: PI_PACKAGE must be name@version' >&2; exit 1; }
name="${PI_PACKAGE%@*}"
version="${PI_PACKAGE##*@}"
pinned="$HOME/${PI_NODE_REL-}"
[[ ! -x "$pinned" ]] || PATH="$(dirname "$pinned"):$PATH"
printf '{"name":"pi-sot-managed-install","version":"%s","private":true,"dependencies":{"%s":"%s"}}\n' "$version" "$name" "$version" > "$HERE/package.json"
(cd "$HERE" && npm install --package-lock-only --ignore-scripts --no-audit --no-fund)
printf 'generated install lock for %s\n' "$PI_PACKAGE"
