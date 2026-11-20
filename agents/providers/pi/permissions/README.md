# Pi permissions

The [Pi adapter](adapter.js) loads from the local package manifest and checks gated tool calls through
[gate.py](gate.py). It uses `ctx.cwd`, independently of event fields, launcher cwd and
`CLAUDE_PROJECT_DIR`. The Pi child environment removes that override; Claude-facing guards and settings
remain unchanged. One Python spawn reuses [the shared scope guards](../../../permissions/README.md) in-process and adds Pi's explicit
instruction-derived rule families. `powershell` is disabled because these guards parse POSIX shells.

| family | instruction owner |
|---|---|
| index, commit, history, remote and working-tree-discard writes | [universal Git/authority rules](../../../AGENTS.md#7-git-workflow) and the consuming project's Git workflow |
| system-wide operations | [universal authorization boundaries](../../../AGENTS.md#2-autonomous-work-scope-and-permission-boundaries) |
| recursive removal and `.git` preservation | universal unknown-work preservation; unchanged shared scope guard |
| protected credential paths and content readers | [universal secrets rules](../../../AGENTS.md#secrets-and-privacy) and the consuming project's secret owner |

At session startup the adapter runs forbidden synthetic cases. `/guard-status` in an interactive Pi
session reports loaded health, interpreter and shell. Missing/failed startup prevents gated calls.
Each call requires a positive marker; denies, missing markers, malformed output, spawn/handler errors
and timeouts block with a reason. A timeout terminates the spawned shell/interpreter tree and reports
whether exit was observed. [Adapter tests](../../../tests/providers/pi/adapter.test.js) exercise a real sleeping
interpreter and native PID checks, separately from injectable timeout-refusal tests.

Run the external loaded check after installation and Pi upgrades on each platform. It exercises the
shared guards through Pi without requiring another provider. When Claude is also installed, run
[the shared selfcheck](../../../permissions/README.md#verifying), which additionally validates Claude
registration and settings.
The acceptance [probe fixture](../../../tests/providers/pi/probe.js) is excluded from the package and loaded explicitly only in
controlled scratch checks. Its output/request limits apply only to acceptance. The acceptance SDK
runner preserves native boundary dispatch and explicitly ends the generation; its transport guard
refuses extra dispatches. [The acceptance owner](../../../tests/providers/pi/README.md#transport-acceptance)
owns those limits and native failure controls.

Residuals remain explicit: startup cannot detect a guard that later wrongly allows without error.
No continuous probing runs. Guards do not inspect scripts, interpreters, `eval`, arbitrary programs,
Git aliases/plumbing, variable/glob-generated paths or implicit recursive searches through protected
directories. Shared rm parsing has deliberate deferrals. Text matching can produce false positives.
Additional extension tools pass through unless explicitly gated. This is accident prevention for
supervised sessions, not OS isolation or unrestricted unattended authorization.
