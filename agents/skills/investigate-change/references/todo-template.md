<!-- Template guidance, not part of the todo: do not copy this comment.

Repository todos contain technical facts, evidence, decisions, and verification.
Do not persist credentials, authentication/access details, account/session identifiers, or narratives of how operational access was authorized or obtained. Record resulting technical observations neutrally; retain only provenance needed to verify them.

Sections in order: Goal / Authority register / Non-goals / Verified evidence / Current architecture and
source of truth / Problem and root cause / Decision (with Premise-KISS gate and Alternatives considered) /
Required invariants / Implementation tasks / Test-first and verification plan (Red and Green evidence) /
Documentation plan / Rollout and rollback / Completion criteria / Review record.
Past ~100 lines add a compact `## Contents` under the status block, per documentation-structure.md. -->

# <Change title>

**Status:** REVIEW REQUIRED  
**Scope:** <affected subsystem or boundary>  
**Stable documentation owner:** <existing doc path, proposed doc path, or `none` with reason>

## Goal

State the observable outcome, not the proposed mechanism. The goal is operator-owned intent, not verified
truth: investigation validates its feasibility, consistency, and verifiability before design. Once validated,
do not silently narrow, replace, or cross it. A `D<n>` constrains how the goal is met and never replaces it;
a goal/`D<n>` conflict is the operator's to resolve.

## Authority register

Operational access authorizations are ephemeral execution context, not task authority, and must not be recorded in this register.

Task-local register of authority for this change. It records explicit operator decisions, operator gates,
and agent assumptions without mixing their authority. Binding `D<n>` entries outrank `## Decision`, the KISS
gate, reviewer findings, and agent preference within their stated scope. Cite `D<n>`/`Q<n>`/`A<n>` elsewhere
in this todo instead of restating them. Silence never promotes an `A<n>` into a `D<n>`. Anything here that
must stay authoritative after this todo is complete moves to its stable owner before `PASS`.

IDs remain stable once assigned. `D<n>` wording is immutable: a changed operator decision gets a new `D<m>`
marked `Supersedes: D<n>`, the old `D<n>` is marked `[SUPERSEDED by D<m>]` with its wording left intact, and
active tasks re-cite the binding entry. `Q<n>` and `A<n>` keep their original statement too, but carry a
lifecycle status that never changes that statement's meaning.

### Operator decisions

Only an explicit human choice enters this section. A reviewer round, a group of accepted
findings, a verification event, an implementation summary, or a correction to the register
itself is **not** a decision and belongs in `## Review record`.

A `D<n>` is binding unless marked. Three marks, and supersession is always written on **both**
entries — the new one says what it supersedes, the old one carries its mark:

- `[SUPERSEDED by D<m>]` — was a real decision, wholly replaced.
- `[SUPERSEDED IN PART by D<m> — <what died>]` — name the dead clause *and* the surviving one in
  the entry's Effect, so neither has to be inferred.
- `[VOID — <why>]` — was never valid authority: never operator-authorized, or recorded in error.
  Leave a one-line tombstone and move the narrative to `## Review record`. Never renumber.
- `[AUTHORITY UNVERIFIED — <what replaced it>]` — non-binding, and provenance that can no longer
  be established either way. Assert neither "valid Decision later superseded" nor "never valid":
  technical merit is not authority, so an entry being a good idea proves nothing about whether a
  human chose it. It is not a Decision but it is a register entry, so it is its own class in the
  census — every `D<n>` is accounted for, with no gaps.

The register is a **state list, not a chronology**: `### Operator decisions` answers one question —
what binds me now — so an entry that stops binding moves to `### No longer binding` below it,
wording intact so every citation stays truthful. A `[SUPERSEDED IN PART]` entry stays in the
binding list, because its surviving clause still binds. The order things happened in is
`## Review record`'s job.

- **D1** <faithful statement of the operator's decision>
  - Effect: <what it constrains or supersedes>
  - Reason: <operator-stated reason, or `not stated`>
  - Date/source: <when known>
- **D2 [SUPERSEDED by D5]** <the decision as it stood; left unedited>
- **D5** <the replacement decision>
  - Supersedes: D2
  - Effect: <what it constrains or supersedes>
  - Reason: <operator-stated reason, or `not stated`>
  - Date/source: <when known>

### Operator gates

- **Q1 [OPEN - BLOCKING]:** <question> - gates: <the specific task or decision it holds>
- **Q2 [OPEN - NON-BLOCKING]:** <question> - default while open: A1
- **Q3 [CLOSED by D5]:** <original question, left intact>

### Working assumptions

An `A<n>` is never authority. Operator confirmation creates a new `D<n>`; the assumption is then marked
resolved, not promoted.

- **A1 [ACTIVE]:** <agent-selected default or unconfirmed premise>
- **A2 [RESOLVED by D5]:** <original assumption, left intact>
- **A3 [REJECTED by evidence]:** <original assumption, left intact> - <what refuted it>

## Non-goals

List nearby work explicitly excluded from this change.

## Verified evidence

For each material fact, cite an exact file, symbol, test, command, log, incident, or runtime observation. Separate:

- **Verified facts**
- **Inferences**
- **Assumptions / unverified areas**
- **Refuted** - what was shown false, and the evidence that killed it. A conclusion retracted here
  stays here so the next reader neither re-derives nor restores it.

## Current architecture and source of truth

Describe only the affected responsibilities, boundaries, data flow, failure domains, and existing owners. Link to stable documentation and implementation entry points instead of duplicating them.

## Problem and root cause

State what is wrong, why it occurs, and why the current evidence supports that conclusion. For a feature, state the concrete capability gap instead.

## Decision

State the smallest recommended design and its integration points.

### Premise / KISS gate

Name the component that already owns the lifecycle and data for this outcome, the moving parts the chosen design removes versus adds (services, processes, ports, protocols, callbacks, lifecycles), and the one capability knowingly given up. Existing machinery is retained only against a concrete requirement stated here.

### Alternatives considered

Include only materially viable alternatives and the concrete reason each is not recommended.

## Required invariants

Number the behavioral, transactional, compatibility, reliability, security, and operational guarantees that must remain true.

## Implementation tasks

Use an ordered checklist. Each task must name the responsibility or integration point, not prescribe speculative edits unsupported by the repository.

- [ ] Add or adjust regression/acceptance evidence.
- [ ] Implement the smallest architecture-aligned change.
- [ ] Cover failure paths and compatibility constraints.
- [ ] Update stable documentation and its router when required.
- [ ] Run the declared verification matrix.
- [ ] Review the final diff against this todo and the stable sources of truth.

## Test-first and verification plan

### Red evidence

For a bug, specify the exact regression test, production-shaped fixture/input, command, and expected failing assertion. The failure must expose the defect rather than a malformed test.

For a feature, refactor, or documentation change, red evidence is of three kinds, and each item
says which it is:

- **Acceptance evidence** measures the requested outcome before and after, wherever the outcome can
  be measured at all. A proxy is named as a proxy; the outcome the operator asked for is the one
  that has to move.
- **Permanent regression guards** are added only for machine-provable contracts whose regression
  risk justifies a test that lives forever. Each is observed failing before the change.
- **Reviewer-checked judgements** — meaning, taste, current truth versus history — are recorded as
  a list the reviewer verifies. They are never encoded as an allowlist test merely to manufacture
  a red case.

Red evidence must be a matrix: one named case per behavior being changed (including E2E-level
ones), each stating the wrong behavior it captures today. Every guard is written and observed
failing before any production code.

### Green evidence

List the exact same regression test plus relevant unit, integration, smoke, static-analysis, build, and runtime checks. State why each test belongs to the change.

## Documentation plan

- **Authoritative stable owner:** `<path>`
- **Router / TOC update:** `<path or none>`
- **Content to add or change:** durable contracts, invariants, architecture, or operations only
- **Duplication avoided:** identify any document that should link rather than restate
- Stable docs, code, comments, tests, and configuration must not reference this todo.

## Rollout and rollback

Include only when deployment, data, compatibility, or operational risk makes it material.

## Completion criteria

Define observable proof required for `PASS`, including exact tests, runtime evidence, documentation state, and absence of unrelated changes.

## Review record

The chronology: one `###` entry per review or operator round, newest last. This section owns history, so every
other section states only current truth — a superseded statement is edited in place there and its story stays
here. Keep a round as a `###` entry under this heading; rounds promoted to their own `##` sections leave the
todo with no navigable spine.

Authority movement is recorded by ID and never restated; a decision's wording lives in `## Authority register`
alone. For example: `D5 added; supersedes D2`, `Q2 closed by D6`, `reviewer finding accepted, ## Decision now
cites D6`.

Before `PASS`, sweep these entries for anything that outlives the change — a root cause, an invariant, an
operational trap — and move each to its stable owner per `## Documentation plan`. What may remain here is
narrative.

### <YYYY-MM-DD> - <what this round was about>

- **Trigger:** the operator's own words, or the symptom as observed.
- **Root cause:** the mechanism. A fix recorded without one is how a cause stays hidden.
- **Fix:** what changed.
- **Verification:** only what moved since `## Test-first and verification plan` — the new cases and their
  counts. Do not restate the standing suite every round.
- **Authority:** `D<n>` added or superseded, gate closed - by ID.

Material changes to goal, decision, scope, invariants, or completion criteria require renewed review before implementation continues.
