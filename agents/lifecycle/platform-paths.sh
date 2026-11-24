# Native Windows profile discovery shared by lifecycle and permission checks.
# The installer host needs POSIX home and link semantics; native Windows Bash cannot
# reach the native link or WSL path owners below.
host_family() {
  case "$(uname -s 2>/dev/null || true)" in
    MINGW*|MSYS*|CYGWIN*) printf 'windows-bash\n' ;;
    *) printf 'posix\n' ;;
  esac
}

windows_profile() {
  local profile cwd=/
  [[ ! -d /mnt/c ]] || cwd=/mnt/c
  profile="$(cd "$cwd" && timeout 20 powershell.exe -NoProfile -NonInteractive -Command '[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false); [Environment]::GetFolderPath("UserProfile")' 2>/dev/null)" || return 1
  profile="${profile//$'\r'/}"
  [[ -n "$profile" && "$profile" != *'%USERPROFILE%'* ]] || return 1
  printf '%s\n' "$profile"
}
