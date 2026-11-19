# Native Windows profile discovery shared by lifecycle and permission checks.
windows_profile() {
  local profile cwd=/
  [[ ! -d /mnt/c ]] || cwd=/mnt/c
  profile="$(cd "$cwd" && timeout 20 cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null)" || return 1
  profile="${profile//$'\r'/}"
  [[ -n "$profile" && "$profile" != *'%USERPROFILE%'* ]] || return 1
  printf '%s\n' "$profile"
}
