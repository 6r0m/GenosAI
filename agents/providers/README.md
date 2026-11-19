# Agent providers

| provider | owns |
|---|---|
| [Claude Code](claude/README.md) | user settings on both sides: the tracked file, its plan and apply, and the drift warning |
| [Codex](codex/README.md) | permission defaults on both sides, projected through the native config writer |
| [Pi](pi/README.md) | native package lifecycle, managed runtime and permission integration |

Shared provider registration and profile selection belong to
[the lifecycle configuration owner](../lifecycle/README.md). Provider handlers reuse its generic
instruction and skill wiring; the shared instruction/search resource uses that handler directly.
