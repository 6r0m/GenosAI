# Component-owned lifecycle resources and runtime pins.
register_provider claude .claude CLAUDE.md whole claude
register_provider codex .codex AGENTS.md individual codex
register_provider shared .agents AGENTS.md shared generic
register_provider pi .pi/agent AGENTS.md package pi

CLAUDE_LIFECYCLE_REL='providers/claude/lifecycle.sh'
CODEX_LIFECYCLE_REL='providers/codex/lifecycle.sh'
PI_LIFECYCLE_REL='providers/pi/lifecycle.sh'
PI_PACKAGE='@earendil-works/pi-coding-agent@1.5.2'
PI_NODE_REL='.nvm/versions/node/v24.8.0/bin/node'
PI_PREFIX_REL='.local/share/pi-sot'
PI_LAUNCHER_REL='.local/bin/pi-sot'
PI_WIN_PREFIX_REL='AppData/Roaming/pi-sot'
PI_WIN_LAUNCHER_REL='AppData/Roaming/npm/pi-sot.cmd'
PI_WIN_BASH_LAUNCHER_REL='AppData/Roaming/npm/pi-sot'
PI_WIN_SHELL_REL='Program Files/Git/bin/bash.exe'
PI_WIN_NODE_REL='Program Files/nodejs/node.exe'
PI_TELEMETRY_VALUE=0
# Pi public defaults live in providers/pi/runtime/profiles.json; config.py composes private input.
# providers/pi/runtime/configure.js owns the connection schema and native projection.
