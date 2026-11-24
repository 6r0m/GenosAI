#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
AI_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
AGENTS_SOT="$AI_ROOT/AGENTS.md"
SKILLS_SOT="$AI_ROOT/skills"
AGENT_IGNORE_SOT="$AI_ROOT/agent-ignore"
BASHRC_BEGIN='# >>> agents SOT: ai/agents/scripts/install.sh >>>'
BASHRC_END='# <<< agents SOT <<<'
FAILED=0
source "$SCRIPT_DIR/registry.sh"
load_registry || { echo 'error: invalid provider/profile configuration' >&2; exit 1; }
source "$SCRIPT_DIR/platform-links.sh"
source "$SCRIPT_DIR/platform-paths.sh"
if [[ "$(host_family)" == windows-bash ]]; then
  echo 'error: run the installer from WSL or Linux, not native Windows Bash; from Windows run it through wsl.exe' >&2
  exit 1
fi
operation="${1-}"; shift
[[ "$operation" == install || "$operation" == uninstall ]] || exit 1
selected='shared'; runtime=0; approve=''; platforms=host
while [[ $# -gt 0 ]]; do
  case "$1" in
    --provider) [[ $# -ge 2 ]] || exit 1; selected="$2"; shift 2 ;;
    --runtime) runtime=1; shift ;;
    --platform) [[ $# -ge 2 && "$2" =~ ^(host|windows|both)$ ]] || { echo "error: --platform takes host, windows or both" >&2; exit 1; }; platforms="$2"; shift 2 ;;
    --approve) [[ $# -ge 2 && "$2" =~ ^[0-9a-f]{12}$ ]] || { echo 'error: --approve takes a 12-character plan id' >&2; exit 1; }
      approve="$2"; shift 2 ;;
    *) echo "error: unknown lifecycle argument $1" >&2; exit 1 ;;
  esac
done
if [[ "$selected" != all ]]; then
  [[ -n "${PROVIDER_DIR[$selected]+yes}" ]] || { echo "error: unknown provider $selected" >&2; exit 1; }
  PROVIDERS=("$selected")
fi
if [[ "$runtime" == 1 && ( -z "$selected" || "${PROVIDER_HANDLER[$selected]}" != pi ) ]]; then
  echo 'error: --runtime requires a selected provider with runtime support' >&2; exit 1
fi
[[ -f "$AGENTS_SOT" && -d "$SKILLS_SOT" && -f "$AGENT_IGNORE_SOT" ]] || exit 1

retire_shared_skill_link() {
  local destination="$1" platform="$2"
  if [[ -L "$destination" && "$(readlink -f "$destination" || true)" == "$SKILLS_SOT" ]]; then
    if [[ "$platform" == windows ]]; then (cd /mnt/c && cmd.exe /c rmdir "$(wslpath -w "$destination")" 2>/dev/null) || rm -- "$destination"
    else rm -- "$destination"; fi
    printf 'retired %s\n' "$destination"
  elif [[ -e "$destination" || -L "$destination" ]]; then printf 'kept    %s (not an SOT link; left alone)\n' "$destination"; fi
}
link_resource() {
  local platform="$1" source="$2" dest="$3" rel="$4" kind="$5"
  if [[ "$operation" == uninstall ]]; then remove_link "$dest" "$([[ "$platform" == windows ]] && echo "$rel" || true)"
  elif [[ "$platform" == wsl ]]; then install_wsl_link "$source" "$dest"
  elif [[ "$kind" == dir ]]; then install_win_dir "$dest" "$rel" "$source"
  else install_win_file "$dest" "$rel" "$source"; fi
}
search_config_matches() {
  [[ ! -L "$1" && -f "$1" ]] && cmp -s -- "$1" <(printf '%s\n' "$2")
}
write_search_config() {
  search_config_matches "$1" "$2" && return 0
  local temporary
  temporary="$(mktemp "$(dirname "$1")/.ripgreprc.XXXXXX")"
  printf '%s\n' "$2" > "$temporary"
  mv -- "$temporary" "$1"
}
shared_search() {
  local platform="$1" home="$2" dir="$3" target="$2/$3/ripgreprc"
  local expected native_target='' current='' native_cwd=/
  [[ ! -d /mnt/c ]] || native_cwd=/mnt/c
  if [[ "$platform" == wsl ]]; then expected="--ignore-file=$home/$dir/agent-ignore"
  else
    native_target="$(wslpath -w "$target")"
    expected="--ignore-file=$(wslpath -w "$AGENT_IGNORE_SOT")"
    current="$(cd "$native_cwd" && powershell.exe -NoProfile -Command "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding(\$false); [Environment]::GetEnvironmentVariable('RIPGREP_CONFIG_PATH','User')" | tr -d '\r')"
  fi
  if [[ "$operation" == install ]]; then
    if [[ -L "$target" ]] || { [[ -e "$target" ]] && ! search_config_matches "$target" "$expected"; }; then
      echo 'error: foreign search configuration left alone' >&2; return 1
    fi
    if [[ "$platform" == windows && -n "$current" && "$current" != "$native_target" ]]; then
      echo 'error: foreign RIPGREP_CONFIG_PATH left alone' >&2; return 1
    fi
  fi
  [[ "${4-}" != preflight ]] || return 0
  if [[ "$platform" == wsl ]]; then
    link_resource "$platform" "$AGENT_IGNORE_SOT" "$home/$dir/agent-ignore" "${dir//\//\\}\\agent-ignore" file
    if [[ "$operation" == install ]]; then
      write_search_config "$target" "$expected"
      install_bashrc_block "$dir"
    else
      if search_config_matches "$target" "$expected"; then rm -- "$target"; fi
      if [[ -f "$home/.bashrc" ]]; then
        local temp; temp="$(mktemp)"
        awk -v b="$BASHRC_BEGIN" -v e="$BASHRC_END" '$0 == b {skip=1;next} $0 == e {skip=0;next} !skip' "$home/.bashrc" > "$temp"
        cat "$temp" > "$home/.bashrc"; rm -- "$temp"
      fi
    fi
  else
    if [[ "$operation" == install ]]; then
      write_search_config "$target" "$expected"
      if [[ -z "$current" ]]; then (cd "$native_cwd" && powershell.exe -NoProfile -Command "[Environment]::SetEnvironmentVariable('RIPGREP_CONFIG_PATH','$native_target','User')" >/dev/null)
      fi
    else
      if search_config_matches "$target" "$expected"; then rm -- "$target"; fi
      if [[ "$current" == "$native_target" ]]; then (cd "$native_cwd" && powershell.exe -NoProfile -Command "[Environment]::SetEnvironmentVariable('RIPGREP_CONFIG_PATH',\$null,'User')" >/dev/null); fi
    fi
  fi
}
generic() {
  local id="$1" platform="$2" home="$3" dir="${PROVIDER_DIR[$1]}" mode="${PROVIDER_SKILLS[$1]}"
  [[ "$mode" != shared || "$operation" != install ]] || shared_search "$platform" "$home" "$dir" preflight
  [[ "$operation" == uninstall ]] || mkdir -p "$home/$dir"
  link_resource "$platform" "$AGENTS_SOT" "$home/$dir/${PROVIDER_FILE[$id]}" "${dir//\//\\}\\${PROVIDER_FILE[$id]}" file
  if [[ "$mode" == whole ]]; then link_resource "$platform" "$SKILLS_SOT" "$home/$dir/skills" "${dir//\//\\}\\skills" dir; fi
  if [[ "$mode" == shared ]]; then
    if [[ "$operation" == install ]]; then retire_shared_skill_link "$home/$dir/skills" "$platform"; else remove_link "$home/$dir/skills" "${dir//\//\\}\\skills"; fi
    shared_search "$platform" "$home" "$dir"
  fi
  if [[ "$mode" == individual ]]; then
    [[ "$operation" == uninstall ]] || mkdir -p "$home/$dir/skills"
    if [[ "$operation" == install ]]; then
      for skill in "$SKILLS_SOT"/*/; do
        [[ -f "$skill/SKILL.md" ]] || continue
        name="$(basename "$skill")"
        link_resource "$platform" "$SKILLS_SOT/$name" "$home/$dir/skills/$name" "${dir//\//\\}\\skills\\$name" dir
      done
    else
      for skill in "$home/$dir/skills"/*; do [[ -L "$skill" ]] || continue; remove_link "$skill" "$([[ "$platform" == windows ]] && echo "${dir//\//\\}\\skills\\$(basename "$skill")" || true)"; done
    fi
    link_resource "$platform" "$SKILLS_SOT/.shared" "$home/$dir/skills/.shared" "${dir//\//\\}\\skills\\.shared" dir
  fi
}
source "$AI_ROOT/$CLAUDE_LIFECYCLE_REL"
source "$AI_ROOT/$CODEX_LIFECYCLE_REL"
source "$AI_ROOT/$PI_LIFECYCLE_REL"

if [[ "$operation" == install ]]; then python3 "$AI_ROOT/config.py" || exit 1; fi
for id in "${PROVIDERS[@]}"; do
  if declare -F "${PROVIDER_HANDLER[$id]}_preflight" >/dev/null; then
    "${PROVIDER_HANDLER[$id]}_preflight" "$id" || exit 1
  fi
done

if [[ "$platforms" != windows ]]; then
  echo "== Host home: $HOME"
  for id in "${PROVIDERS[@]}"; do "${PROVIDER_HANDLER[$id]}" "$id" wsl "$HOME"; done
fi
if [[ "$platforms" != host ]]; then
  WIN_PROFILE="$(windows_profile || true)"
  if [[ -n "$WIN_PROFILE" ]]; then
    WIN_HOME="$(wslpath -u "$WIN_PROFILE")"; AGENTS_SOT_WIN="$(wslpath -w "$AGENTS_SOT")"
    echo "== Windows profile: $WIN_HOME"
    for id in "${PROVIDERS[@]}"; do "${PROVIDER_HANDLER[$id]}" "$id" windows "$WIN_HOME"; done
  else
    echo 'warn: could not resolve Windows profile; Windows side skipped' >&2
    FAILED=1
  fi
fi
# A handler may define <handler>_finalize for work that needs every platform at once, after both passes.
for id in "${PROVIDERS[@]}"; do
  if declare -F "${PROVIDER_HANDLER[$id]}_finalize" >/dev/null; then "${PROVIDER_HANDLER[$id]}_finalize" "$id"; fi
done
if [[ "${#ELEVATED_QUEUE[@]}" -gt 0 ]]; then
  BATCH="$WIN_HOME/AppData/Local/Temp/agents-sot-links.cmd"
  { printf '@echo off\r\nchcp 65001 >nul || exit /b 1\r\n'; printf '%s || exit /b 1\r\n' "${ELEVATED_QUEUE[@]}"; } > "$BATCH"
  echo 'Queued NT links require the existing elevated link batch; re-run to verify.'
  printf 'Run from an elevated Windows terminal: %s\n' "$(wslpath -w "$BATCH")"
  FAILED=1
fi
[[ "$FAILED" == 0 ]] || exit 1
echo "Done: $operation ${selected:-all configured providers}."
