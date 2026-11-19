#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
AI_ROOT="$(cd -- "$HERE/../../.." && pwd -P)"
source "$AI_ROOT/lifecycle/registry.sh"
load_registry
[[ $# == 1 ]] || { echo 'usage: run.sh <fresh directory below repository tmp>' >&2; exit 1; }
if [[ "${OSTYPE-}" == msys* || "${OSTYPE-}" == cygwin* ]]; then
  task_node="/c/$PI_WIN_NODE_REL"
  task_index="$(cygpath -w "$HOME/$PI_WIN_PREFIX_REL/node_modules/${PI_PACKAGE%@*}/dist/index.js")"
  task_cli="$(cygpath -w "$HOME/$PI_WIN_PREFIX_REL/node_modules/${PI_PACKAGE%@*}/dist/bundle/cli.js")"
  task_root="$(cygpath -w "$AI_ROOT")";task_dir="$(cygpath -w "$HOME/${PROVIDER_DIR[pi]}")"
  task_fixture="$(cygpath -w "$1")";task_repo="$(cygpath -w "$AI_ROOT/..")"
else
  task_node="$HOME/$PI_NODE_REL"
  task_index="$HOME/$PI_PREFIX_REL/node_modules/${PI_PACKAGE%@*}/dist/index.js"
  task_cli="$HOME/$PI_PREFIX_REL/node_modules/${PI_PACKAGE%@*}/dist/bundle/cli.js"
  task_root="$AI_ROOT";task_dir="$HOME/${PROVIDER_DIR[pi]}";task_fixture="$1";task_repo="$(cd "$AI_ROOT/.." && pwd -P)"
fi
platform=wsl
[[ "${OSTYPE-}" != msys* && "${OSTYPE-}" != cygwin* ]] || platform=windows
local_json="$(bash "$AI_ROOT/permissions/run-guard.sh" ../../config.py pi --platform "$platform")"
# The profile owner validates the connection schema and pinned capability without displaying credentials.
config_args=("$task_dir" "$task_repo" "$task_cli" "${PI_PACKAGE##*@}")
resolved="$("$task_node" "$AI_ROOT/providers/pi/runtime/configure.js" install "${config_args[@]}" --local <<<"$local_json")" || exit 1
IFS=$'\t' read -r profile provider model thinking <<<"$resolved"
exec "$task_node" "$HERE/live.js" "$task_index" "$task_root" "$task_fixture" "$task_dir" "$profile" "$provider" "$model" "$thinking"
