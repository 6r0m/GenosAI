# Claude Code provider lifecycle: the generic instruction and skill links on each platform, then one plan,
# confirmation and apply of the tracked user settings across every platform this run reached.
CLAUDE_SETTINGS_SIDES=()

claude_preflight() {
  [[ "$operation" != install ]] || python3 "$AI_ROOT/providers/claude/settings.py" validate
}

claude() {
  local id="$1" platform="$2" home="$3"
  generic "$id" "$platform" "$home"
  local target="$home/${PROVIDER_DIR[$id]}/settings.json"
  if [[ "$operation" == install ]]; then CLAUDE_SETTINGS_SIDES+=("$platform" "$target")
  else printf 'kept    %s (Claude settings are left in place on uninstall)\n' "$target"; fi
}

# Runs once after both platform passes, so every side is validated and shown in one plan before any is written.
claude_finalize() {
  [[ "$operation" == install && "${#CLAUDE_SETTINGS_SIDES[@]}" -gt 0 ]] || return 0
  local -a args=(apply)
  local i
  for ((i = 0; i < ${#CLAUDE_SETTINGS_SIDES[@]}; i += 2)); do
    args+=(--side "${CLAUDE_SETTINGS_SIDES[i]}" "${CLAUDE_SETTINGS_SIDES[i+1]}")
  done
  [[ -z "$approve" ]] || args+=(--approve "$approve")
  python3 "$AI_ROOT/providers/claude/settings.py" "${args[@]}" || FAILED=1
}
