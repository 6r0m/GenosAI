codex() {
  local id="$1" platform="$2" home="$3" task_codex native_home native_cwd=/ probe shell_home shell_codex account
  generic "$id" "$platform" "$home"
  if [[ "$operation" == uninstall ]]; then
    printf 'kept    %s (Codex settings are left in place on uninstall)\n' "$home/${PROVIDER_DIR[$id]}/config.toml"
    return
  fi
  if [[ "$platform" == wsl ]]; then
    task_codex="$(type -P codex || true)"
    if [[ -z "$task_codex" ]]; then
      account="$(account_home || true)"
      if [[ -n "$account" && "${HOME%/}" == "${account%/}" ]]; then
        # A bash launched from Windows starts WSL without the login profile. Ask the
        # account login shell once, but only accept a runtime resolved while that
        # shell keeps the selected home: a profile that switches HOME must not
        # select another account's executable.
        probe="$(timeout 20 bash -lc 'printf "home:%s\n" "$HOME"; printf "codex:%s\n" "$(type -P codex || true)"' 2>/dev/null || true)"
        shell_home="$(printf '%s\n' "$probe" | sed -n 's/^home://p' | tail -n 1)"
        shell_codex="$(printf '%s\n' "$probe" | sed -n 's/^codex://p' | tail -n 1)"
        if [[ "${shell_home%/}" == "${HOME%/}" ]]; then task_codex="$shell_codex"; fi
        [[ ! -f "$task_codex" ]] || printf 'ok      %s (Codex runtime from the login shell)\n' "$task_codex"
      fi
    fi
    native_home="$home/${PROVIDER_DIR[$id]}"
  else
    [[ ! -d /mnt/c ]] || native_cwd=/mnt/c
    task_codex="$(cd "$native_cwd" && cmd.exe /d /c where codex 2>/dev/null | tr -d '\r' |
      awk 'tolower($0) ~ /\.(exe|cmd|bat)$/ && !found { print; found=1 }')" || true
    [[ -z "$task_codex" ]] || task_codex="$(wslpath -u "$task_codex")"
    native_home="$(wslpath -w "$home/${PROVIDER_DIR[$id]}")"
  fi
  if [[ -z "$task_codex" || ! -f "$task_codex" ]]; then
    if [[ "$platform" == wsl ]]; then
      printf 'warn: Codex settings skipped on wsl: Codex executable not found on the installer PATH; add its directory to PATH and rerun\n' >&2
    else
      printf 'warn: Codex settings skipped on windows: Codex executable not found on the Windows PATH; repair PATH and rerun\n' >&2
    fi
    FAILED=1
    return
  fi
  python3 "$AI_ROOT/providers/codex/settings.py" apply "$home/${PROVIDER_DIR[$id]}" \
    --codex "$task_codex" --native-home "$native_home" || { FAILED=1; return; }
}
