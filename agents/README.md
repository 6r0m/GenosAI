# agents/ — Shared coding-agent environment

This directory owns the shared coding-agent environment: universal instructions,
reusable skills, permission guards, provider configuration, installation/removal,
and their verification across repositories and supported agent tools.

Its child owners below define their own contracts; `agents/` keeps their common
scope and integration together. Tools consume its canonical instructions and skills
through links or Pi's local package. Product-specific tooling belongs to
`integrations/`; run orchestration is outside this domain. The
[GenosAI router](../README.md) reaches the other project owners.

## Contents

- [Layout](#layout)
- [Local configuration](#local-configuration)
- [Wiring and Pi connections](#wiring-and-pi-connections)
- [Skills](#skills)
- [Update / uninstall](#update--uninstall)

## Layout

```
agents/
├── AGENTS.md      # Universal agent instructions (global SOT for all repos)
├── agent-ignore   # paths agent search sweeps must not surface (ripgrep, machine-wide)
├── package.json   # Pi local-package loading contract
├── config.py      # ignored JSON/JSONC input and validated sparse additions
├── vendor/        # pinned comment parser
├── skills/        # Global agent skills (Claude Code + Codex + Pi), one dir per skill
│   ├── .shared/   # Principles referenced by the skills (dot-dir: not a skill)
│   └── synced/    # Claude Code's claude.ai skill cache via .claude/skills (ignored; never in a Codex route)
├── permissions/   # shared guards and cross-platform selfcheck
├── lifecycle/     # shared dispatch and the single provider/profile configuration
├── providers/     # provider domains: native settings, runtime and permissions
├── scripts/       # thin install/uninstall interfaces
└── tests/         # deterministic checks over everything above
```

Permission rules, the `PreToolUse` guards that express what a rule cannot, and
the cross-platform self-check: [permissions/README.md](permissions/README.md).
These are registered in the user-level `settings.json` on both sides, so they
apply to every session on the machine rather than to this repository alone.
The Claude Code provider, one of [the agent providers](providers/README.md), owns those settings and
applies them.

Conformance, ownership, routing, template and cost checks: [tests/README.md](tests/README.md) —
`bash agents/tests/run-tests.sh`, no venv required.

## Local configuration

The [commented template](../config.local.example.jsonc) explains every shared section and
optional usage. [Parser dependency](vendor/README.md) owns the pinned JSONC implementation.

[Private settings contract](configuration.md) owns private deltas, validation, and their relationship to
component defaults. The local file stays outside the tracked source.

## Wiring and Pi connections

Pi's local loading contract is owned by [package.json](package.json).

Install/uninstall interfaces are owned by [scripts/README.md](scripts/README.md).
Shared dispatch, agent-integration profiles and runtime pins belong to [lifecycle/README.md](lifecycle/README.md).
Pi connection profiles live with the Pi provider's runtime owner.
Provider implementations belong to [providers/README.md](providers/README.md).
Pi consumes the shared instructions and local package manifest; its provider owns runtime and permissions. Pi invokes skills as
`/skill:<name>` and also discovers `~/.agents/skills`; that route must not expose the synced cache.

## Skills

| skill | owns |
|---|---|
| [investigate-change](skills/investigate-change/SKILL.md) | producing one reviewable todo, never the change |
| [implement-approved-change](skills/implement-approved-change/SKILL.md) | building and proving an approved todo |
| [architect](skills/architect/SKILL.md) | judging shape, read-only |
| [drive-browser](skills/drive-browser/SKILL.md) | browser mechanics on this machine; no repository analysis |
| [frontend-design](skills/frontend-design/SKILL.md) | UX/UI design, interaction, cross-screen consistency and rendered critique |
| [web-design-review](skills/web-design-review/SKILL.md) | checking changed web-UI code against pinned interface guidelines |
| [cinematic-capture-director](skills/cinematic-capture-director/SKILL.md) | directing and capturing footage of a real 3D world |

Skills are available for explicit invocation and for model selection based on their
descriptions. The contract inside
`implement-approved-change` keeps investigation distinct from implementation by
requiring an explicitly approved todo.

`argument-hint` is a Claude Code extension; the portable Agent Skills spec allows
only `name`, `description`, `license`, `compatibility`, `metadata` and
`allowed-tools`, and packaging fails hard on anything else. It is the single field
standing between these skills and full portability, and it costs nothing but an
autocomplete hint. `architect` is
read-only and may be reached by description.

```text
# Codex
$investigate-change investigate <request>; write todo/<name>.md
$implement-approved-change todo/<name>.md
$architect <plan|diff|request>

# Claude Code
/investigate-change investigate <request>; write todo/<name>.md
/implement-approved-change todo/<name>.md
/architect <plan|diff|request>
```

Shared rules live in `skills/.shared/`, one file per concern:

| file | owns |
|---|---|
| [engineering-change-principles.md](skills/.shared/engineering-change-principles.md) | engineering policy |
| [review-contract.md](skills/.shared/review-contract.md) | how work is judged |
| [documentation-structure.md](skills/.shared/documentation-structure.md) | document shape and navigation; routes to the copyable [document templates](skills/.shared/templates/architecture-structure.md) |
| [content-rules.md](skills/.shared/content-rules.md) | what a document and a code comment may say |

Global policy applicability and adapter loading are defined by
[the universal policy-context contract](AGENTS.md#policy-context).
`investigate-change`, `implement-approved-change` and `architect` also specify shared-policy
loads in their invocation workflows. Other skills do not specify those loads themselves.

## Update / uninstall

Tools read instructions/skills through the SOT links or Pi's registered local package. New individual
Codex skill links require re-running the lifecycle interface. Runtime/package updates and scoped
rollback belong to the lifecycle and provider owners above; Pi permission checks after upgrades
belong to its provider. Remote/cloud sessions need their own local installation because machine-local links are absent.
