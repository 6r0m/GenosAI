# Shared agent lifecycle

[providers.conf.sh](providers.conf.sh) is the single operator-editable source for registered providers,
resource paths and runtime pins. Interfaces and managed launchers read it through
[registry.sh](registry.sh). [dispatch.sh](dispatch.sh) selects the operation and provider handler;
[platform-links.sh](platform-links.sh) owns WSL and Windows link mechanics;
[platform-paths.sh](platform-paths.sh) owns native Windows profile discovery. Pi connection profiles are
owned by the Pi runtime owner: [runtime README](../providers/pi/runtime/README.md), whose `profiles.json` and
`configure.js` own the connection schema and its validation.

Generic instruction and skill wiring stays here. Provider-specific lifecycle implementations live in
[the providers owner](../providers/README.md); each receives the selected operation, platform and home.
Shared input validation and optional provider preflights run before installation mutates links.
Shared search setup refuses foreign `ripgreprc` files, symlinks and conflicting Windows environment
settings before changing its resources. Removal deletes only an exact managed configuration.

## Install and remove

Run from WSL:

```bash
bash agents/scripts/install.sh
bash agents/scripts/install.sh --provider pi --runtime
bash agents/scripts/uninstall.sh --provider pi
```

Without selection, install/uninstall dispatch shared instruction/search resources on the host.
Selection touches only that provider. Pi rollback must select Pi so Claude/Codex and shared
resources survive. Add `--runtime` to selected Pi uninstall to remove its owned npm package as well;
operator credentials and foreign files remain. An absent runtime skips package removal accurately but
still removes owned links/configuration. Unsupported operations and invalid descriptors refuse.
Explicit `--platform both` targets WSL and native Windows, including selected-provider operations.
An unavailable Windows profile returns failure and reports the skipped side; completed WSL work can
remain. Partial operations do not print `Done`. A handler may define `<handler>_finalize`, which runs once
after both platform passes, for work that needs every platform at once; the Claude Code handler plans and
applies its settings for both sides there.

On WSL, runtime installation uses the configured Node/prefix without changing system Node, npm defaults,
PATH order or shell profiles. Native Windows installation uses its existing Node and user npm prefix.
NT file links need Developer Mode or the existing elevated link batch. Junctions need a native-drive
source; UNC directory sources require elevated NT directory links. Real files are preserved; install
retains the existing replacement mechanics for conflicting links. Uninstall removes only SOT-owned
links. Codex keeps individual skill links plus `.shared`; Claude keeps the whole skills directory.
The shared search resource configures ripgrep and retires an SOT-wide `.agents/skills` link, so Codex
cannot recursively discover Claude's synced cache. Existing Claude/Codex lifecycle outcomes are covered
by [installer tests](../tests/test_install.py).

Codex's selected installation also projects the defaults owned by
[its provider](../providers/codex/README.md), using each platform's existing native runtime.


## Shared resource contracts

Windows consumers require native NT links/junctions; WSL `ln -s` on the Windows drive makes LX links
that native tools cannot read. The platform helper therefore uses native `mklink` and queues links
that require elevation.

Skills reference shared policy through `../.shared/`, staying inside a Windows junction. Codex's
individual skill routes need a sibling `.shared` link so lexical parent resolution reaches that policy.
A `../../` reference escapes the junction and breaks on Windows.

Claude's whole-directory skills link loads newly added skills automatically and sends edits made
through that link into the canonical working tree. Codex needs new individual links after adding a
skill. Instructions and existing skill edits are read through their links; restart Codex if an update
is not detected. `codex debug prompt-input` checks its discovered sources without calling a model.

The shared search resource uses ripgrep's config rather than Git's `core.excludesFile`, so the search
filter cannot silently exclude tracked work from Git. A filtered sweep does not prove absence;
[agent-ignore](../agent-ignore) owns its escape routes, including explicit file reads, naming a filtered
directory and `rg --no-ignore-files`. Plain `--no-ignore` does not lift that configured filter.

## Explicit setup selection

No arguments selects shared instructions/search wiring on the current Linux/WSL host only.
Choose a provider with `--provider claude|codex|pi`; `--provider all` explicitly requests every provider
and installs Pi without requiring connection input. `--platform windows|both` opts into WSL-to-Windows discovery.
An unavailable requested Windows profile is a failed/partial operation. Ordinary Linux setup does
not call Windows tools. Native Windows Bash installation is not a claimed acceptance target.
Pi installation requires a supported Node interpreter and npm for runtime acquisition. A private connection
and readable credential are required only for model sessions; `pi-sot --version` and `--help` work without
them. `--runtime` explicitly opts into dependency acquisition. Keep provider/runtime pins in the
existing registry; optional local/native state never belongs in that registry.
