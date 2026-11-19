# Shared configuration reader; interfaces and launchers use the same contract.
declare -a PROVIDERS=()
declare -A PROVIDER_DIR=() PROVIDER_FILE=() PROVIDER_SKILLS=() PROVIDER_HANDLER=()
REGISTRY_ERROR=0
register_provider() {
  [[ "$1" =~ ^[a-z][a-z0-9-]*$ && -z "${PROVIDER_DIR[$1]+yes}" && -n "$2" && "$2" != /* && "$2" != *..* && "$3" =~ ^[A-Za-z0-9._-]+$ ]] || { REGISTRY_ERROR=1; return 1; }
  PROVIDERS+=("$1")
  PROVIDER_DIR[$1]="$2"; PROVIDER_FILE[$1]="$3"; PROVIDER_SKILLS[$1]="$4"; PROVIDER_HANDLER[$1]="$5"
}
load_registry() {
  source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/providers.conf.sh"
  [[ "$REGISTRY_ERROR" == 0 ]] || return 1
  for id in "${PROVIDERS[@]}"; do
    [[ "${PROVIDER_SKILLS[$id]}" =~ ^(whole|individual|shared|package|none)$ && "${PROVIDER_HANDLER[$id]}" =~ ^(generic|pi|claude|codex)$ ]] || return 1
  done
  local task_path
  for task_path in "$CLAUDE_LIFECYCLE_REL" "$CODEX_LIFECYCLE_REL" "$PI_LIFECYCLE_REL" "$PI_NODE_REL" "$PI_PREFIX_REL" "$PI_LAUNCHER_REL" "$PI_WIN_PREFIX_REL" "$PI_WIN_LAUNCHER_REL" "$PI_WIN_BASH_LAUNCHER_REL" "$PI_WIN_SHELL_REL" "$PI_WIN_NODE_REL"; do
    [[ -n "$task_path" && "$task_path" != /* && "$task_path" != *..* ]] || return 1
  done
}
