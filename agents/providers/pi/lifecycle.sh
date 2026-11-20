# Validate setup prerequisites and any configured connection before provider links change.
pi_preflight() {
  [[ "$operation" == install ]] || return 0
  local input config_node="$HOME/$PI_NODE_REL" native_profile
  input="$(python3 "$AI_ROOT/config.py" pi)" || return 1
  if [[ "$platforms" != windows ]]; then
    [[ -x "$config_node" ]] || config_node="$(command -v node || true)"
    [[ -x "$config_node" ]] || { echo 'error: install Linux Node 22.19+ and npm in your user environment, then retry the Pi install' >&2; return 1; }
    if [[ "$runtime" == 1 && ! -x "$(dirname "$config_node")/npm" ]] && ! command -v npm >/dev/null; then
      echo 'error: npm required for selected Linux Pi runtime acquisition' >&2; return 1
    fi
  else
    config_node="/mnt/c/$PI_WIN_NODE_REL"
  fi
  if [[ "$platforms" != host ]]; then
    native_profile="$(windows_profile || true)"
    if [[ -n "$native_profile" ]]; then
      [[ -x "/mnt/c/$PI_WIN_NODE_REL" && -x "/mnt/c/$PI_WIN_SHELL_REL" ]] || {
        echo 'error: install native Windows Node 22.19+ and Git Bash before selecting Windows Pi' >&2; return 1;
      }
    fi
  fi
  [[ -x "$config_node" ]] || { echo 'error: native Windows Node required for Pi configuration preflight' >&2; return 1; }
  local config_script="$AI_ROOT/providers/pi/runtime/configure.js"
  [[ "$platforms" != windows ]] || config_script="$(wslpath -w "$config_script")"
  "$config_node" "$config_script" schema --setup --local <<<"$input"
}

pi_runtime() {
  local action="$1" platform="$2" task_node="$3" task_prefix="$4"
  if [[ "$action" == install ]]; then
    # The checked-in lock is the derived installation artifact for PI_PACKAGE: it pins the whole
    # dependency tree, so npm ci cannot resolve a floating transitive pi-ai out from under the
    # capability check.
    local task_npm=''
    if [[ "$platform" == wsl ]]; then
      task_npm="$(dirname "$task_node")/npm"
      [[ -x "$task_npm" ]] || task_npm="$(command -v npm || true)"
      [[ -x "$task_npm" ]] || { echo 'error: npm required for Pi runtime acquisition' >&2; return 1; }
    fi
    mkdir -p "$task_prefix" || return 1
    cp -- "$AI_ROOT/providers/pi/runtime/install-lock/package.json" "$AI_ROOT/providers/pi/runtime/install-lock/package-lock.json" "$task_prefix/" || return 1
    if [[ "$platform" == wsl ]]; then
      PATH="$(dirname "$task_node"):$PATH" "$task_npm" ci --prefix "$task_prefix" --ignore-scripts --no-audit --no-fund --engine-strict
    else
      (cd /mnt/c && cmd.exe /c npm ci --prefix "$(wslpath -w "$task_prefix")" --ignore-scripts --no-audit --no-fund --engine-strict)
    fi
  else
    # The prefix is dedicated to this managed runtime, so removal owns exactly the generated tree and
    # leaves unrelated sibling files alone. npm uninstall can leave node_modules behind, which the
    # ownership preflight would then read as a foreign prefix on the next install.
    rm -rf -- "$task_prefix/node_modules" || return 1
    rm -f -- "$task_prefix/package.json" "$task_prefix/package-lock.json" || return 1
  fi
}

pi() {
  local id="$1" platform="$2" home="$3" task_node task_cli task_prefix task_launcher task_repo task_agent
  local owner task_telemetry_owner="$home/${PROVIDER_DIR[$id]}/.agents-sot-telemetry"
  if [[ "$platform" == wsl ]]; then owner="$home/$PI_PREFIX_REL/.agents-sot-owner"
  else owner="$home/$PI_WIN_PREFIX_REL/.pi-agents-sot-owner"; fi
  if [[ "$runtime" == 1 ]]; then
    if [[ -e "$owner" ]] && ! grep -qxF "$AI_ROOT" "$owner"; then echo 'error: foreign runtime owner left alone' >&2; return 1; fi
    if [[ "$operation" == uninstall && ! -f "$owner" ]]; then echo 'error: refusing removal of unowned Pi runtime' >&2; return 1; fi
    local runtime_prefix
    if [[ "$platform" == wsl ]]; then runtime_prefix="$home/$PI_PREFIX_REL"; else runtime_prefix="$home/$PI_WIN_PREFIX_REL"; fi
    if [[ "$operation" == install && ! -f "$owner" ]]; then
      for managed in node_modules package.json package-lock.json; do
        [[ ! -e "$runtime_prefix/$managed" && ! -L "$runtime_prefix/$managed" ]] || { echo 'error: existing unowned Pi runtime artifact left alone' >&2; return 1; }
      done
    fi
  fi
  if [[ "$platform" == wsl ]]; then
    task_node="$home/$PI_NODE_REL"; task_prefix="$home/$PI_PREFIX_REL"; task_launcher="$home/$PI_LAUNCHER_REL"
    task_repo="$(cd "$AI_ROOT/.." && pwd -P)"; task_agent="$home/${PROVIDER_DIR[$id]}"
    task_cli="$task_prefix/node_modules/${PI_PACKAGE%@*}/dist/bundle/cli.js"
  else
    task_node="/mnt/c/$PI_WIN_NODE_REL"
    task_prefix="$home/$PI_WIN_PREFIX_REL"; task_launcher="$home/$PI_WIN_LAUNCHER_REL"
    task_repo="$(wslpath -w "$AI_ROOT/..")"; task_agent="$(wslpath -w "$home/${PROVIDER_DIR[$id]}")"
    task_cli="$(wslpath -w "$task_prefix/node_modules/${PI_PACKAGE%@*}/dist/bundle/cli.js")"
  fi
  if [[ "$platform" == wsl && ! -x "$task_node" ]]; then task_node="$(command -v node || true)"; fi
  local local_json config_operation=pi
  [[ "$operation" != uninstall ]] || config_operation=pi-uninstall
  local_json="$(bash "$AI_ROOT/permissions/run-guard.sh" ../../config.py "$config_operation" --platform "$platform")" || return 1
  local native_cli="$task_cli" agent_root="$AI_ROOT"
  [[ "$platform" != windows ]] || agent_root="$(wslpath -w "$AI_ROOT")"
  local available=0
  if [[ -f "$task_cli" || ( "$platform" == windows && -f "$(wslpath -u "$task_cli")" ) ]]; then available=1; fi
  if [[ "$operation" == install ]]; then
    if [[ -e "$task_launcher" ]] && ! grep -qF 'agents SOT launcher' "$task_launcher"; then echo 'error: foreign Pi launcher left alone' >&2; return 1; fi
    if [[ "$platform" == windows ]]; then
      if [[ -e "$home/$PI_WIN_BASH_LAUNCHER_REL" ]] && ! grep -qF 'agents SOT launcher' "$home/$PI_WIN_BASH_LAUNCHER_REL"; then echo 'error: foreign Git Bash launcher left alone' >&2; return 1; fi
      local telemetry_current
      telemetry_current="$(cd /mnt/c && powershell.exe -NoProfile -Command "[Environment]::GetEnvironmentVariable('PI_TELEMETRY','User')" | tr -d '\r')"
      if [[ -n "$telemetry_current" && "$telemetry_current" != "$PI_TELEMETRY_VALUE" ]]; then echo 'error: foreign PI_TELEMETRY left alone' >&2; return 1; fi
    fi
    local config_script="$AI_ROOT/providers/pi/runtime/configure.js" config_node="$task_node"
    [[ "$platform" != windows ]] || config_script="$(wslpath -w "$config_script")"
    if [[ ! -x "$config_node" && "$platform" == wsl ]]; then config_node="$(command -v node || true)"; fi
    [[ -x "$config_node" ]] || { echo 'error: configured Node required for Pi install preflight' >&2; return 1; }
    local version="${PI_PACKAGE##*@}"
    local -a config_args=("$task_agent" "$task_repo")
    local -a runtime_args=()
    # An acquisition replaces the installed CLI, so that preflight proves schema, credential and
    # projections only; the new CLI meets the exact pin after npm ci. Without acquisition the installed
    # runtime must already match the pin.
    if [[ "$runtime" != 1 && "$available" == 1 ]]; then runtime_args=("$native_cli" "$version"); fi
    "$config_node" "$config_script" validate "${config_args[@]}" "${runtime_args[@]}" --setup --local <<<"$local_json" || return 1
    if [[ "$runtime" == 1 ]]; then
      local fresh_runtime=0
      [[ -f "$owner" ]] || fresh_runtime=1
      if ! pi_runtime install "$platform" "$task_node" "$task_prefix"; then
        if [[ "$fresh_runtime" == 1 ]]; then
          echo "Pi runtime installation failed on $platform; removing generated artifacts" >&2
          pi_runtime uninstall "$platform" "$task_node" "$task_prefix" || { echo 'error: failed install cleanup failed' >&2; return 1; }
        fi
        return 1
      fi
      printf '%s\n' "$AI_ROOT" > "$owner"
      if ! "$task_node" "$config_script" validate "${config_args[@]}" "$native_cli" "$version" --setup --local <<<"$local_json"; then
        if [[ "$fresh_runtime" == 1 ]]; then
          echo "Pi preflight failed on $platform; removing the newly owned runtime" >&2
          pi_runtime uninstall "$platform" "$task_node" "$task_prefix" || { echo 'error: newly owned runtime cleanup failed' >&2; return 1; }
          rm -- "$owner"
        fi
        return 1
      fi
      runtime_args=("$native_cli" "$version")
      available=1
    fi
    generic "$id" "$platform" "$home"
    if [[ "$available" == 1 ]]; then
      PI_CODING_AGENT_DIR="$task_agent" PI_TELEMETRY="$PI_TELEMETRY_VALUE" "$task_node" "$native_cli" install "$agent_root"
      "$task_node" "$config_script" install "${config_args[@]}" "${runtime_args[@]}" --setup --local <<<"$local_json" >/dev/null
      mkdir -p "$(dirname "$task_launcher")"
      if [[ -e "$task_launcher" ]] && ! grep -qF 'agents SOT launcher' "$task_launcher"; then echo 'error: foreign Pi launcher left alone' >&2; return 1; fi
      if [[ "$platform" == wsl ]]; then
        printf '#!/usr/bin/env bash\n# agents SOT launcher\nexec /bin/bash %q "$@"\n' "$AI_ROOT/providers/pi/runtime/launch.sh" > "$task_launcher"; chmod +x "$task_launcher"
      else
        printf '@echo off\r\nrem agents SOT launcher\r\n"%s" "%s" %%*\r\n' "$(wslpath -w "/mnt/c/$PI_WIN_SHELL_REL")" "$(wslpath -w "$AI_ROOT/providers/pi/runtime/launch.sh")" > "$task_launcher"
        local bash_launcher="$home/$PI_WIN_BASH_LAUNCHER_REL"
        if [[ -e "$bash_launcher" ]] && ! grep -qF 'agents SOT launcher' "$bash_launcher"; then echo 'error: foreign Git Bash launcher left alone' >&2; return 1; fi
        printf '#!/usr/bin/env bash\n# agents SOT launcher\nexec bash %q "$@"\n' "$(wslpath -w "$AI_ROOT/providers/pi/runtime/launch.sh")" > "$bash_launcher"
        if [[ -z "$telemetry_current" ]]; then
          (cd /mnt/c && powershell.exe -NoProfile -Command "[Environment]::SetEnvironmentVariable('PI_TELEMETRY','$PI_TELEMETRY_VALUE','User')" >/dev/null)
          printf '%s\n' "$AI_ROOT" > "$task_telemetry_owner"
        fi
      fi
    else echo "skipped Pi registration on $platform: runtime absent; run install.sh --provider $id --runtime"; fi
  else
    if [[ "$available" == 1 ]]; then
      PI_CODING_AGENT_DIR="$task_agent" PI_TELEMETRY="$PI_TELEMETRY_VALUE" "$task_node" "$native_cli" remove "$agent_root"
      local config_script="$AI_ROOT/providers/pi/runtime/configure.js"; [[ "$platform" != windows ]] || config_script="$(wslpath -w "$config_script")"
      "$task_node" "$config_script" uninstall "$task_agent" "$task_repo" --local <<<"$local_json"
    else
      echo "skipped Pi package removal on $platform: runtime absent; cleaning owned links"
      if [[ -d "$home/${PROVIDER_DIR[$id]}" ]]; then
        local config_node="$task_node" config_script="$AI_ROOT/providers/pi/runtime/configure.js"
        [[ -x "$config_node" ]] || config_node="$(command -v node || true)"
        [[ -x "$config_node" ]] || { echo 'error: Node required to remove managed Pi configuration' >&2; return 1; }
        [[ "$platform" != windows ]] || config_script="$(wslpath -w "$config_script")"
        "$config_node" "$config_script" uninstall "$task_agent" "$task_repo" --local <<<"$local_json"
      fi
    fi
    generic "$id" "$platform" "$home"
    if [[ -f "$task_launcher" ]] && grep -qF 'agents SOT launcher' "$task_launcher"; then rm -- "$task_launcher"; fi
    if [[ "$platform" == windows ]]; then
      if [[ -f "$home/$PI_WIN_BASH_LAUNCHER_REL" ]] && grep -qF 'agents SOT launcher' "$home/$PI_WIN_BASH_LAUNCHER_REL"; then rm -- "$home/$PI_WIN_BASH_LAUNCHER_REL"; fi
      if [[ -f "$task_telemetry_owner" ]] && grep -qxF "$AI_ROOT" "$task_telemetry_owner"; then
        (cd /mnt/c && powershell.exe -NoProfile -Command "if ([Environment]::GetEnvironmentVariable('PI_TELEMETRY','User') -eq '$PI_TELEMETRY_VALUE') {[Environment]::SetEnvironmentVariable('PI_TELEMETRY',\$null,'User')}" >/dev/null)
        rm -- "$task_telemetry_owner"
      fi
    fi
    if [[ "$runtime" == 1 ]]; then
      if [[ "$platform" == wsl && -f "$task_prefix/.agents-sot-owner" ]] && grep -qxF "$AI_ROOT" "$task_prefix/.agents-sot-owner"; then
        pi_runtime uninstall "$platform" "$task_node" "$task_prefix"
        rm -- "$task_prefix/.agents-sot-owner"
      elif [[ "$platform" == windows && -f "$task_prefix/.pi-agents-sot-owner" ]] && grep -qxF "$AI_ROOT" "$task_prefix/.pi-agents-sot-owner"; then
        pi_runtime uninstall "$platform" "$task_node" "$task_prefix"; rm -- "$task_prefix/.pi-agents-sot-owner"
      else echo 'error: refusing removal of unowned Pi runtime' >&2; return 1; fi
    fi
  fi
}
