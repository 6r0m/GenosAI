codex() {
  local id="$1" platform="$2" home="$3" task_codex native_home native_cwd=/
  generic "$id" "$platform" "$home"
  if [[ "$operation" == uninstall ]]; then
    printf 'kept    %s (Codex settings are left in place on uninstall)\n' "$home/${PROVIDER_DIR[$id]}/config.toml"
    return
  fi
  if [[ "$platform" == wsl ]]; then
    task_codex="$(type -P codex || true)"
    native_home="$home/${PROVIDER_DIR[$id]}"
  else
    [[ ! -d /mnt/c ]] || native_cwd=/mnt/c
    task_codex="$(cd "$native_cwd" && cmd.exe /d /c where codex 2>/dev/null | tr -d '\r' |
      awk 'tolower($0) ~ /\.(exe|cmd|bat)$/ && !found { print; found=1 }')" || true
    [[ -z "$task_codex" ]] || task_codex="$(wslpath -u "$task_codex")"
    native_home="$(wslpath -w "$home/${PROVIDER_DIR[$id]}")"
  fi
  if [[ -z "$task_codex" || ! -f "$task_codex" ]]; then
    printf 'warn: Codex settings skipped on %s: native runtime absent\n' "$platform" >&2
    FAILED=1
    return
  fi
  python3 "$AI_ROOT/providers/codex/settings.py" apply "$home/${PROVIDER_DIR[$id]}" \
    --codex "$task_codex" --native-home "$native_home" || { FAILED=1; return; }
}
