# Shared link mechanics for registry-owned lifecycle resources.
install_wsl_link() {
  local source="$1"
  local destination="$2"

  if [[ -L "$destination" ]]; then
    local current
    current="$(readlink -f -- "$destination" || true)"
    if [[ "$current" == "$source" ]]; then
      printf 'ok      %s -> %s\n' "$destination" "$source"
      return
    fi
    rm -- "$destination"
  elif [[ -e "$destination" ]]; then
    printf 'error   refusing to replace non-symlink: %s\n' "$destination" >&2
    FAILED=1
    return
  fi

  ln -s -- "$source" "$destination"
  printf 'linked  %s -> %s\n' "$destination" "$source"
}

install_bashrc_block() {
  local rc="$HOME/.bashrc" stripped rebuilt resource_dir="$1"
  [[ -f "$rc" ]] || : > "$rc"
  stripped="$(mktemp)"
  rebuilt="$(mktemp)"

  # Drop any previous block first, then re-prepend the current one, so changing
  # what the block contains cannot leave a second stale copy behind.
  awk -v b="$BASHRC_BEGIN" -v e="$BASHRC_END" '
    $0 == b { skip = 1; next }
    $0 == e { skip = 0; next }
    !skip
  ' "$rc" > "$stripped"

  {
    printf '%s\n' "$BASHRC_BEGIN"
    printf 'export RIPGREP_CONFIG_PATH="$HOME/%s/ripgreprc"\n' "$resource_dir"
    printf '%s\n' "$BASHRC_END"
    cat "$stripped"
  } > "$rebuilt"

  if cmp -s "$rc" "$rebuilt"; then
    printf 'ok      %s (RIPGREP_CONFIG_PATH block)\n' "$rc"
    rm -f -- "$stripped" "$rebuilt"
    return
  fi

  # Refuse to write unless removing the block again reproduces the file we read:
  # proves the edit adds the block and changes nothing else.
  local verify
  verify="$(mktemp)"
  awk -v b="$BASHRC_BEGIN" -v e="$BASHRC_END" '
    $0 == b { skip = 1; next }
    $0 == e { skip = 0; next }
    !skip
  ' "$rebuilt" > "$verify"
  if ! cmp -s "$stripped" "$verify"; then
    printf 'error   refusing to edit %s: block round-trip failed\n' "$rc" >&2
    FAILED=1
    rm -f -- "$stripped" "$rebuilt" "$verify"
    return
  fi

  # Redirect into the existing file: keeps its inode, mode and ownership.
  cat "$rebuilt" > "$rc"
  printf 'wrote   %s (RIPGREP_CONFIG_PATH block)\n' "$rc"
  rm -f -- "$stripped" "$rebuilt" "$verify"
}
win_linktype() {
  (cd /mnt/c && powershell.exe -NoProfile -Command \
    "(Get-Item -LiteralPath '$1' -Force -ErrorAction SilentlyContinue).LinkType" 2>/dev/null | tr -d '\r')
}

# Junctions need no privileges; replace anything that is not a working NT link.
install_win_dir() {
  local destination="$1"
  local dest_win source source_win
  dest_win="$WIN_PROFILE\\$2"
  source="${3:-$SKILLS_SOT}"
  source_win="$(wslpath -w "$source")"

  if [[ -L "$destination" ]]; then
    local current linktype
    current="$(readlink -f -- "$destination" || true)"
    linktype="$(win_linktype "$dest_win")"
    if [[ "$current" == "$source" && ( "$linktype" == "Junction" || "$linktype" == "SymbolicLink" ) ]]; then
      printf 'ok      %s -> %s\n' "$destination" "$source"
      return
    fi
    (cd /mnt/c && cmd.exe /c rmdir "$dest_win" 2>/dev/null) || rm -- "$destination"
  elif [[ -e "$destination" ]]; then
    printf 'error   refusing to replace non-symlink: %s\n' "$destination" >&2
    FAILED=1
    return
  fi

  # Junctions cannot target UNC paths: an ext4-hosted repo (\\wsl.localhost\...)
  # needs an elevated directory symlink instead.
  if [[ "$source_win" == \\\\* ]]; then
    printf 'queued  %s (dir symlink needs elevation; UNC target)\n' "$destination"
    ELEVATED_QUEUE+=("mklink /D \"$dest_win\" \"$source_win\"")
    return
  fi

  # Paths as separate argv words: embedded \" quotes get mangled by WSL interop.
  (cd /mnt/c && cmd.exe /c mklink /J "$dest_win" "$source_win" >/dev/null)
  printf 'junct   %s -> %s\n' "$destination" "$source"
}

# NT links that require elevation (or Developer Mode) are queued into one batch.
ELEVATED_QUEUE=()

install_win_file() {
  local destination="$1"
  local dest_win source="${3:-$AGENTS_SOT}" source_win
  dest_win="$WIN_PROFILE\\$2"
  source_win="$(wslpath -w "$source")"

  if [[ -L "$destination" ]]; then
    local current linktype
    current="$(readlink -f -- "$destination" || true)"
    linktype="$(win_linktype "$dest_win")"
    if [[ "$current" == "$source" && "$linktype" == "SymbolicLink" ]]; then
      printf 'ok      %s -> %s\n' "$destination" "$source"
      return
    fi
    rm -- "$destination"
  elif [[ -e "$destination" ]]; then
    printf 'error   refusing to replace non-symlink: %s\n' "$destination" >&2
    FAILED=1
    return
  fi

  # Unprivileged attempt works when Windows Developer Mode is enabled.
  if (cd /mnt/c && cmd.exe /c mklink "$dest_win" "$source_win" >/dev/null 2>&1); then
    printf 'linked  %s -> %s\n' "$destination" "$source"
  else
    printf 'queued  %s (needs elevation)\n' "$destination"
    ELEVATED_QUEUE+=("mklink \"$dest_win\" \"$source_win\"")
  fi
}

remove_link() {
  local destination="$1"
  local win_rel="${2:-}"
  [[ -L "$destination" ]] || return 0
  local current
  current="$(readlink -f -- "$destination" || true)"
  if [[ "$current" != "$AI_ROOT"/* ]]; then
    printf 'kept    %s (points elsewhere)\n' "$destination"
    return 0
  fi
  if [[ -n "$win_rel" && -d "$destination" ]]; then
    # Windows junctions must be removed with rmdir, not rm.
    (cd /mnt/c && cmd.exe /c rmdir "$WIN_PROFILE\\$win_rel" 2>/dev/null) || rm -- "$destination"
  else
    rm -- "$destination"
  fi
  printf 'removed %s\n' "$destination"
}
