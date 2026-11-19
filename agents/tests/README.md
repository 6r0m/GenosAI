# Skill-system tests

Run from the AI source root:

```bash
bash agents/tests/run-tests.sh
```

No virtualenv and no network: the suite uses the standard library and local tools for markdown
checks, permission guards, and isolated installer fixtures.

| file | proves |
|---|---|
| `test_private_config.py` | the browser example is disabled; AI-local ignore rules exclude private configuration and backups in a standalone disposable repository; canonical skill resolution works through a POSIX symlink or a real native Windows junction with spaces |
| `test_preparation.py` | conservative public defaults, external credential references and model-helper argument/refusal behavior (model scripts run on Linux/WSL) |
| `test_pi_paths.py` | shared WSL/native drive projection and canonical ownership fallback during broken-local removal |
| `test_release.py` | private-file export exclusion, forbidden artifacts, personal-path controls, scanner detection/error distinction, force-added keys, history, and clean shared setup/removal |
| `test_platform_paths.py` | native profile discovery preserves spaces and refuses missing, unexpanded, or failed results using controlled command doubles |
| `test_conformance.py` | every skill parses; `name` matches its directory and is spec-legal; `description` is present and within the 1024-character cap; the body stays under 500 lines; global instructions reference both canonical engineering/review policies; every relative link resolves; no path uses `../../`, which breaks the Windows junction; a reference over 100 lines exposes its sections, as a `## Contents` heading or as the guidance comment a template carries instead. References do not prove effective context or agent compliance |
| `test_ownership.py` | deterministic sentinels across universal instructions and shared policy files: each **selected** critical shared rule is still present and appears in only one policy file. Not semantic proof — a differently worded duplicate passes, and an unlisted rule is unguarded; architect review owns that |
| `test_routing.py` | the standalone project README chain holds for every **router node** (a maintained directory carrying its own `README.md`): one route each, reachable from its parent, and no route that skips a level. A real owner that never declared a README is invisible here by construction. Also the mechanical half of the link rule: no text promising a directory while pointing at a file, no placeholder text, no phrase pointing at two targets. Whether a link says what is on the other side is semantic and stays a review job |
| `test_templates.py` | every template opens with guidance that says it is not part of the document, its declared section list matches its actual headings, the structure template still leaves the relationship graph to the main view and cites relationships owned elsewhere |
| `test_agent_ignore.py` | the search-sweep filter, run through the real `rg` against a built tree: every finished-todo naming variation is hidden (affix on either segment, any casing, any depth), the near-misses stay visible, no pattern fails to parse — a malformed glob would disable the filter silently — and the documented escape hatches still hold (`--no-ignore-files` lifts it, `--no-ignore` does not) |
| `test_install.py` | the installer's WSL half, run from a copy of `agents/` into a sandbox home with a planted non-skill tree. All three global instruction links resolve to the canonical file. `~/.codex/skills` gets one link per real skill plus `.shared`, and Codex's own `.system/` and local skills stay untouched. No link is left at `~/.agents/skills`, while a real directory there is kept and reported. A second run changes nothing, and uninstall removes only our links. Claude settings are applied only through an approved plan, keep Claude Code's own keys, and survive uninstall. Every run gets an explicit environment that cannot reach the Windows half; junctions and Windows' lexical `..` are out of its reach |
| `test_claude_settings.py` | the Claude settings owner. Only tracked top-level keys change, Claude Code's own keys and order survive, and nothing is written without a confirmed or approved plan. A stale plan, an unparsable side or a refused second write leaves the files byte-identical or reported. The plan never prints credential-like values or command lines. The session-start warning prints nothing on a clean side, only a `systemMessage` on drift, and warns rather than staying silent when the script, interpreter or adapter is missing or broken |
| `test_codex_settings.py` | Codex's native version-checked config writer receives only owned keys; matching settings skip writes, conflicting permission profiles refuse, and overridden results cannot report success. Native-runtime checks cover existing and empty disposable homes, TOML preservation, idempotence and refusal. Windows command shims use the native interpreter with spaces in the path and the selected Windows home; no model request is made |
| [Provider tests](providers/README.md) | provider permission, configuration and native runtime checks |
| `report_cost.py` | not a test — the diffable cost table: tokens loaded per disclosure level, the worst case before any repository file is read, and how many owners are reachable by traversal |
| `skilltree.py` | the shared definitions — what a skill, a link, a router node, and a route are — with generated synced/trash trees excluded and maintained documents retained as a traversal control |

## What this suite does not cover

It checks the system's **shape**, deterministically. Whether a fresh agent reaches the
right answer, and what that costs, is measured separately in
[evaluation/README.md](evaluation/README.md) — real agent runs against this repository, with the
private receipts recorded against explicit source identities.

`test_routing.py` checks the standalone source root; directory exclusions are relative to that root,
so putting a checkout under a temporary directory cannot make discovery silently empty.


## Native Windows

Run the full WSL and native Windows suites sequentially. Some fixtures share fixed paths under
repository `tmp/agent-tests/`; concurrent platform runs can delete or overwrite each other's test state.

Run the Python suite with Windows Python from Git Bash and the JavaScript suite with native Node.
Gate/adapter tests must execute, including the sleeping-process fixture; WSL-only installer tests are
explicitly skipped on Windows. Local fake-provider transport uses native Pi and synthetic keys only.
See [provider verification](providers/README.md) for the required installed route and bounded
paid-smoke procedure. Passing deterministic tests does not establish direct API authentication.
