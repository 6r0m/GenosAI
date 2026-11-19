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
# Native subcommands are recognized only at argv[0], before ordinary prompt parsing.
case "${1-}" in
  list)
    if [[ -n "$selected_profile" ]]; then "$task_node" "$SCRIPT_DIR/configure.js" resolve "${config_args[@]}" "${selection_args[@]}" --local <<<"$local_json" >/dev/null; fi
    exec "$task_node" "$task_cli" "$@" ;;
  install|remove|uninstall|update|config|mcp|auth)
    echo "error: '$1' mutates native state outside the managed SOT route; edit the ignored local pi object for connections, or use scripts/install.sh and scripts/uninstall.sh for lifecycle operations. Raw pi is the unmanaged route." >&2
    exit 1 ;;
esac
# One install validates and projects one profile snapshot, then returns its launch selection.
resolved="$("$task_node" "$SCRIPT_DIR/configure.js" install "${config_args[@]}" "${selection_args[@]}" --local <<<"$local_json")" || exit 1
IFS=$'\t' read -r active provider model thinking <<<"$resolved"
[[ -n "$active" && -n "$provider" && -n "$model" ]] || { echo 'error: Pi profile resolution produced no connection' >&2; exit 1; }
launch_args=(--provider "$provider" --model "$model")
[[ -z "$thinking" ]] || launch_args+=(--thinking "$thinking")
exec "$task_node" "$task_cli" "${launch_args[@]}" "$@"
