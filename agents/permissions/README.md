# Permissions

What Claude Code and Pi may do on this machine, and the guards that enforce path scope.
Claude hooks and Pi's local-package adapter have separate failure behaviour.

**The model in one line:** a tripwire, not a lock. The guards stop an agent from
*accidentally* deleting or editing outside the repo and scratch areas; an agent
that deliberately routes around them (`python`, `bash -c`) can. That trade is
deliberate, and it means a guard that silently stops running looks exactly like one
that is working. `selfcheck.sh` tells the difference for the scripts, and
`live-check.sh` for Claude Code still calling them. Registered in the user-level
`settings.json` on each explicitly selected platform, so the hooks apply across repositories
for that installation. Those registrations
are values in [the Claude Code provider's tracked settings](../providers/claude/README.md),
which selected-provider installation projects and validates on its selected platforms.

Public settings use ordinary approval and an empty allowlist. Broader access or an unattended
permission mode requires an explicit private choice through [local configuration](../configuration.md).
The guards complement that choice; they do not grant permission to execute commands.

## Layout

```
permissions/
├── run-guard.sh   # picks a working Python and launches one guard
├── selfcheck.sh   # proves the guards actually run on this platform
├── live-check.sh  # proves a real Claude Code session still uses them (paid)
└── guards/        # PreToolUse / PermissionRequest decision scripts
```

| guard | event | owns |
|---|---|---|
| [`guards/repo_guard.py`](guards/repo_guard.py) | `PreToolUse` · `Edit\|Write\|NotebookEdit` | file edits stay inside the repo and sanctioned scratch areas |
| [`guards/bash_rm_guard.py`](guards/bash_rm_guard.py) | `PreToolUse` · `Bash` | a recursive delete may not target anything outside that scope |
| [`guards/rm_scope_allow.py`](guards/rm_scope_allow.py) | `PermissionRequest` · `Bash` | under `bypassPermissions`, refuses every prompt with a next step; never approves ([prompts in an unattended session](#prompts-in-an-unattended-session)) |

## Why guards and not just deny rules

Deny rules match command text. That is enough for a fixed target such as
`sudo` or `git push --force`, and not enough for anything that needs a path
resolved or an exception carved out:

- **A deny rule cannot carry an allowlist exception.** "Delete inside the repo
  but nowhere else" is not expressible, so `Bash(rm -rf /*)` blocked every
  absolute recursive delete including scratch directories.
- **It matches text, not meaning.** That same rule never saw `/bin/rm -rf /etc`.
  It blocked the honest path and not the workaround, which trains exactly the
  behaviour it was meant to prevent.
- **`ask` rules are no soft guard under `bypassPermissions` either.** Claude
  Code still prompts for an explicit `ask` rule in that mode, but nobody is
  there to answer. For a Bash or Monitor command `rm_scope_allow.py` refuses
  that prompt (see below), so there an `ask` rule behaves as a deny; on any
  other tool nothing answers it, and an unattended session waits.

The guards resolve paths instead - relative targets against the session's cwd,
`..` collapsed, Windows and WSL spellings folded together - which is why `deny`
keeps only the narrow literal cases. Symlinks are resolved through `realpath`
so a temp-named link cannot stand in for a path outside the scope.

File-edit scratch roots derive from the current home/temp owners and validated additions in
[local configuration](../configuration.md). Invalid local input returns a deny even for an in-repo
edit; it is distinct from the documented unexpected-runtime failure behavior. Operator-specific
repository roots are not shipped as defaults. The selfcheck discovers Windows settings through the
native profile owner and preserves spaces in each settings path.

**In scope**, for `bash_rm_guard.py`, means strictly inside the working repo, or
below a temp-named directory through a named child of it: `/tmp/job/x` is one
job's area, `/tmp/*` is every session's scratch and is not. The working repo is
the project folder Claude Code reports, unless that folder is a home folder, a
folder above one, or a filesystem or drive root (on WSL also `/mnt`, a drive
under it, or a Windows profile). A session started there has no working repo,
only the temp-named areas, because taking such a folder as the repo would put a
whole home or drive in scope. `repo_guard.py` keeps its own scope, the session's
working directory, even there: an edit changes one file per call, and deny
rules block edits to `.ssh`, `.gnupg`, `.aws`, `.mcp.json` and Claude Code's own
settings and hooks wherever they are.

## Prompts in an unattended session

Some commands make Claude Code ask a human even under `bypassPermissions`. The
[permission modes](https://code.claude.com/docs/en/permission-modes) docs list
them: an `rm`/`rmdir` of a critical path (the root and its direct children,
home, the working directory and its parents, a glob directly under an unguarded
variable), an explicit `ask` rule, a read outside the working directories while
`blockReadsOutsideWorkingDirectories` is on. Claude Code's own parser decides
this, in whatever shell form it reads. In a bypass session nobody is there to
answer, so the session would stop.

`rm_scope_allow.py` runs on `PermissionRequest`, which fires exactly when Claude
Code is about to ask. Under `bypassPermissions` it refuses every such prompt, for
any Bash or Monitor command, without interrupting the agent. The refusal says
how to rework a removal (a literal path in scope, or a variable guarded as
`${VAR:?}`), so the agent replans instead of waiting. In any other mode it gives
no answer, and the user decides. The filename is the one both user-level
`settings.json` files register.

It never approves. The payload carries the command, not the reason Claude Code
asked, so an approval could grant a different part of the command than the one
the hook looked at: `rm -f ./tmp/x; curl … | sh` is one prompt. The cost is one
replan for an in-scope removal that Claude Code flags, such as `rm -rf "$D"/*`,
which runs as `rm -rf "${D:?}"/*` or with a literal path.

Both refusals, this one and `bash_rm_guard.py`'s, name one place for transient
files that already exists and is meant for them. They follow the order in
[`../AGENTS.md`](../AGENTS.md): the repo's `tmp/` when git ignores it, else the
session `scratchpad_dir` Claude Code reports, else none, only an approach without
a temporary file. The hooks run in every repository, so a hint that named a
missing or tracked `tmp/` would plant a stray directory there.

What this cannot cover:

- **The hook is not running** - a crash, a timeout, no working Python. The prompt
  then appears, as it fails open by design (see below).
- **Commands that never prompt.** Neither Claude Code's check nor the guards read
  inside `sh -c`, `bash -c`, `python -c` or `eval`, so a removal written that way
  runs with no prompt and no guard, `bash -c 'rm -rf /something'` included. That
  is the tripwire trade described at the top.

## Which tools count as a shell

Three tools reach a shell, and a guard bound to only one of them is no guard.
This was the single most repeated defect in building this: each new entry point
looked fine, because a guard that never runs and a guard that allows are
indistinguishable from inside a session.

| tool | status |
|---|---|
| `Bash` | guarded |
| `Monitor` | guarded; normal client permission checks still apply, with the hook matcher `Bash\|Monitor` |
| `PowerShell` | disabled, not guarded - see below |

`Monitor` needed no new parsing: same `tool_input.command`, same POSIX shell, so
it reuses `bash_rm_guard.py` through the matcher and the guards' `SHELL_TOOLS`.

Neither Bash nor Monitor has a whole-tool allow rule in public defaults. A Monitor command
may therefore request approval under the client's current mode. Private allow rules are an
explicit operator preference; deny rules and `PreToolUse` guards continue to apply. The
unattended-session behavior above applies only when that mode was explicitly selected.

`PowerShell` is different. It speaks `Remove-Item`, not `rm`, so pointing the
existing guard at it would return "no decision" for every destructive command -
false assurance, worse than no coverage. Rather than maintain a second parser
for a tool this setup reaches through Bash anyway, it is switched off twice:

- `env.CLAUDE_CODE_USE_POWERSHELL_TOOL: "0"` stops it being offered. It is
  enabled by default on Windows when Git Bash is installed, for claude.ai and
  Console accounts, so leaving this unset is not a neutral choice.
- a whole-tool `PowerShell` deny rule blocks it even if the env is overridden.
  Only bare `PowerShell` or `PowerShell(*)` counts - `PowerShell(Remove-Item *)`
  leaves every other command open.

`check-registration.py` asserts the posture above, and only that: it knows the
three surfaces named here. It cannot discover a command-executing tool that
Claude Code adds later - that needs this table and `EXPECTED` in the checker to
be reviewed and extended by hand. Given the history above, treat any new tool
that carries a `command` in its input as a shell surface until shown otherwise.

## Fail-open, deliberately

The Claude-facing guards and launcher exit 0 and print valid JSON no matter what goes
wrong. Pi's adapter instead requires a positive marked decision, as described below. `{}` means "no decision, normal permission rules apply". This is a guard
against accidents, not a security boundary - an agent that means to delete can
call Python directly, and a real boundary needs OS-level controls.

The cost of that choice is that a guard which never ran looks exactly like one
that allowed the command. `selfcheck.sh` distinguishes them for the scripts,
which is why it must be run on both platforms. `live-check.sh` does the same for
Claude Code itself still calling the hooks (see Verifying).

`PreToolUse` treats **exit 2 as blocking**, so a guard that dies noisily blocks
the tool call everywhere on the machine. Two consequences are wired in:

- Settings invoke `bash run-guard.sh <guard>`, never the `.py` directly. Bash
  reports 127 for a missing script and Python reports 2, and only 2 blocks - so
  a moved or deleted guards directory degrades to "no decision" instead of
  bricking every session. This is not hypothetical; renaming this directory
  while settings pointed at it blocked Bash and Edit in every open session.
- `run-guard.sh` checks the guard file exists before handing it to Python.

**Order matters when moving anything here:** create the new path, repoint
settings, verify with `selfcheck.sh`, and only then remove the old path. The
window between moving files and updating settings is a machine-wide outage.

## Verifying

Run `selfcheck.sh` on **both** WSL and Git Bash after any of these - each one
has broken a guard silently before:

- editing anything under `permissions/`
- changing the tracked Claude settings and installing them, or editing a
  project `.claude/settings.local.json` - deny rules union across scopes
- upgrading Claude Code - new command-running tools (`Monitor`, `PowerShell`)
  arrived this way and bypassed guards bound to `Bash`
- installing, removing or re-pathing Python on Windows

```bash
bash agents/permissions/selfcheck.sh          # WSL
```

Run it again under Git Bash on Windows, where `/e/...` replaces `/mnt/e/...`.
From WSL that needs no second terminal:

```bash
"/mnt/c/Program Files/Git/bin/bash.exe" -lc \
  "cd '<checkout-as-a-Git-Bash-path>' && bash agents/permissions/selfcheck.sh"
```

Windows is the side that fails, and quietly: `python3` there resolves to the
Microsoft Store alias, which exits 49 without running anything.
`run-guard.sh` picks an interpreter by executing it, so it skips that stub -
[`../tests/test_bash_rm_guard.py`](../tests/test_bash_rm_guard.py) pins the
behaviour with a stub that reproduces it on any platform.
For native Windows Python it explicitly converts the script path with `cygpath` or WSL's
`wslpath`, including when MSYS automatic argument conversion is disabled. Mapping failures keep
the launcher's observable, non-blocking no-decision result; they do not become Python's exit 2.

Behavioural checks live in that same test file and, for the prompt answer, in
[`../tests/test_rm_scope_allow.py`](../tests/test_rm_scope_allow.py). Both run
with the rest of the suite: `bash agents/tests/run-tests.sh`. Run them under
Windows Python too, where paths are spelled with drives and the hint's `git`
lookup goes through Git Bash.

After **upgrading Claude Code**, also run `live-check.sh` from WSL. The checks
above prove the scripts work; they cannot prove Claude Code still calls them.
An upgrade could stop sending the prompts it cannot skip to `rm_scope_allow.py`,
and every unattended session would stall again with every other check green.
The script runs one headless bypass session per platform with the build the VS
Code extension uses, and judges the recorded tool results, not the model's
summary. Each session is a short paid Sonnet run, capped at $1, with no MCP
servers and no saved session history. The streams stay in the repo's ignored
`tmp/live-check/`, and `--parse <run.jsonl> <wsl|windows>` re-checks a saved one.
A target is required, so a bare run starts nothing. It also starts nothing
while any probe's removal target exists, as seen by the shell that would run it
(on Windows, Git Bash at its standard location), so a regressed guard has
nothing real to delete.

```bash
bash agents/permissions/live-check.sh both      # or: wsl | windows
```

VS Code updates the extension on its own, so an upgrade can pass unnoticed.
`live-check.sh --status` costs nothing. It compares each platform's installed
build with the newest saved run, and says when a live check is due or when the
last one failed. `selfcheck.sh` prints it when run under WSL, as a report, not
a failure: an unchecked build is unproven, not broken.


## Pi integration

[Pi's permission owner](../providers/pi/permissions/README.md) owns its adapter, rule entry and
fail-closed contract. It calls this directory's unchanged interpreter launcher and reuses the shared
scope guards in-process. The shared selfcheck includes its startup probe.
