#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
AI_ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd -P)"
source "$AI_ROOT/lifecycle/registry.sh"
load_registry
if [[ "${OSTYPE-}" == msys* || "${OSTYPE-}" == cygwin* ]]; then
  task_node="/c/$PI_WIN_NODE_REL"
  task_cli="$HOME/$PI_WIN_PREFIX_REL/node_modules/${PI_PACKAGE%@*}/dist/bundle/cli.js"
  task_root="$(cygpath -w "$AI_ROOT/..")"
  task_dir="$(cygpath -w "$HOME/${PROVIDER_DIR[pi]}")"
else
  task_node="$HOME/$PI_NODE_REL"
  [[ -x "$task_node" ]] || task_node="$(command -v node || true)"
  task_cli="$HOME/$PI_PREFIX_REL/node_modules/${PI_PACKAGE%@*}/dist/bundle/cli.js"
  task_root="$(cd "$AI_ROOT/.." && pwd -P)"
  task_dir="$HOME/${PROVIDER_DIR[pi]}"
fi
[[ -x "$task_node" && -f "$task_cli" ]] || { echo 'error: Pi runtime unavailable; run install.sh --provider pi --runtime' >&2; exit 1; }
export PI_TELEMETRY="$PI_TELEMETRY_VALUE"
export PI_CODING_AGENT_DIR="$task_dir"
platform=wsl
[[ "${OSTYPE-}" != msys* && "${OSTYPE-}" != cygwin* ]] || platform=windows
unset PI_SOT_PLUGINS
local_json="$(bash "$AI_ROOT/permissions/run-guard.sh" ../../config.py pi --platform "$platform")"
selected_profile=''
# Only the leading managed selector is consumed; native option values and prompts stay opaque.
case "${1-}" in
  --profile)
    [[ $# -ge 2 && -n "$2" && "$2" != -* ]] || { echo 'error: --profile requires a profile ID' >&2; exit 1; }
    selected_profile="$2"; shift 2 ;;
  --profile=*)
    selected_profile="${1#--profile=}"
    [[ -n "$selected_profile" ]] || { echo 'error: --profile requires a profile ID' >&2; exit 1; }
    shift ;;
esac
case "${1-}" in
  --profile|--profile=*) echo 'error: specify --profile only once, before native arguments' >&2; exit 1 ;;
esac
config_args=("$task_dir" "$task_root" "$task_cli" "${PI_PACKAGE##*@}")
selection_args=()
[[ -z "$selected_profile" ]] || selection_args=("$selected_profile")
# Read-only startup checks do not select or project a connection.
if [[ $# == 1 && ( "$1" == --version || "$1" == --help || "$1" == -h ) && -z "$selected_profile" ]]; then
  "$task_node" "$SCRIPT_DIR/configure.js" validate "$task_dir" "$task_root" "$task_cli" "${PI_PACKAGE##*@}" --setup --local <<<"$local_json" >/dev/null
  exec "$task_node" "$task_cli" "$@"
fi
# Native subcommands are recognized only at argv[0], before ordinary prompt parsing.
case "${1-}" in
  list)
    resolved="$("$task_node" "$SCRIPT_DIR/configure.js" inspect "${config_args[@]}" "${selection_args[@]}" --local -- "$@" <<<"$local_json")"
    IFS=$'\t' read -r active provider model selected_dir thinking <<<"$resolved"
    [[ -n "$selected_dir" ]] || { echo 'error: Pi inspection directory missing' >&2; exit 1; }
    export PI_CODING_AGENT_DIR="$selected_dir"
    exec "$task_node" "$task_cli" "$@" ;;
  install|remove|uninstall|update|config|mcp|auth)
    echo "error: '$1' mutates native state outside the managed SOT route; edit the ignored local pi object for connections, or use scripts/install.sh and scripts/uninstall.sh for lifecycle operations. Raw pi is the unmanaged route." >&2
    exit 1 ;;
esac
# One validation and projection supplies both the route and its optional extensions.
resolved="$("$task_node" "$SCRIPT_DIR/configure.js" launch "${config_args[@]}" "${selection_args[@]}" --local -- "$@" <<<"$local_json")" || exit 1
IFS=$'\t' read -r -a selection <<<"$resolved"
[[ ${#selection[@]} -ge 5 ]] || { echo 'error: Pi profile resolution produced no connection' >&2; exit 1; }
export PI_CODING_AGENT_DIR="${selection[2]}"
launch_args=(--provider "${selection[0]}" --model "${selection[1]}")
[[ "${selection[3]}" == - ]] || launch_args+=(--thinking "${selection[3]}")
[[ "${selection[4]}" == - ]] || export PI_SOT_PLUGINS="${selection[4]}"
for extension in "${selection[@]:5}"; do launch_args+=(--extension "$extension"); done
exec "$task_node" "$task_cli" "${launch_args[@]}" "$@"
