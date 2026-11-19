---
name: investigate-change
description: Produce or update one reviewable implementation todo for a requested repository change, grounded in real code and architecture, before changes. Use when the requested deliverable is an implementation todo or plan for later approval. Do not implement the change; read-only architectural judgment belongs to architect.
argument-hint: "<change request> [todo path]"
---

# Investigate change

Investigate the requested change against the repository's real architecture and produce a precise implementation todo for human review. Do not implement the change in this phase.

Read these before proceeding — the first two on every run, the last two when the change touches
documentation or code comments:

| what you will find | file |
|---|---|
| the engineering policy: KISS/SOLID/YAGNI, the reliability guard, one owner per durable fact | `../.shared/engineering-change-principles.md` |
| how work is judged: evidence stance, the counter-evidence loop, the authority vocabulary, verdicts | `../.shared/review-contract.md` |
| where a document lives and how it is reached: the README chain, the architecture address, link text | `../.shared/documentation-structure.md` |
| what a document and a comment may say, and how the two divide the work | `../.shared/content-rules.md` |

## Boundary

- Read-only repository investigation is allowed, including running existing tests and diagnostic commands.
- Do not modify production code, tests, configuration, stable docs, generated files, dependencies, or build outputs intentionally.
- The only intended repository edit is creating or updating the single requested transient todo.
- Do not stage, commit, push, or discard unrelated user changes.
- Stop after the todo and investigation report are complete. File existence is not approval to implement.

## Workflow

### 0. Establish task authority

Do this before the design gate in step 3. The entries land in the todo's `## Authority register`, written in step 4.

- Capture every material explicit operator decision relevant to this change as `D<n>`. Operational access authorizations are execution context, not task authority, and are not `D<n>` decisions. Preserve each decision's meaning; do not strengthen, weaken, or invent a rationale. Record `Reason: not stated` when the operator gave none.
- When updating an existing todo, promote clearly attributable operator decisions buried elsewhere in it into `D<n>` and replace the duplicated authority with a reference to the entry.
- Record questions requiring operator input as `Q<n>` with a lifecycle status (`OPEN - BLOCKING`, `OPEN - NON-BLOCKING`, `CLOSED by D<n>`). Mark one blocking only when its answer materially changes the named task, architecture, safety, or an irreversible outcome.
- Record agent-selected defaults and unconfirmed premises as `A<n>` with a status (`ACTIVE`, `RESOLVED by D<n>`, `REJECTED by evidence`). Silence never converts an assumption into an operator decision; operator confirmation creates a new `D<n>` and marks the `A<n>` resolved.
- IDs are stable and statements are never rewritten. When the operator changes direction, add a new `D<n>` marked `Supersedes: D<m>`, mark `D<m>` `[SUPERSEDED by D<n>]`, and leave its wording intact so existing citations stay truthful.
- Binding `D<n>` entries outrank the agent's recommendation, KISS preference, reviewer findings, and `## Decision` within their stated scope.

### 1. Establish repository context

1. Read applicable global and repository instructions such as `AGENTS.md`, `CLAUDE.md`, and more specific nested guidance.
2. Find the documentation router or nearest subsystem README and identify the stable source of truth for the affected concern.
3. Inspect the relevant architecture, code paths, interfaces, configuration, tests, fixtures, runtime scripts, and error handling.
4. Use history, blame, incidents, logs, or previous regression tests when they materially explain why the current mechanism exists.
5. Record unrelated dirty working-tree state and leave it untouched.

### 2. Verify the premise

- Reproduce the issue or establish concrete repository evidence where practical.
- Determine whether the requested change matches the actual problem and current architecture.
- Validate the stated goal and each binding `D<n>` against the evidence for feasibility, consistency with accepted contracts and safety constraints, and verifiability. Where they are incompatible with the evidence or with each other, do not silently override either side; stop the affected path and surface the conflict for operator resolution.
- Identify existing components that already own the responsibility or can be safely extended.
- Search for duplicate implementations before proposing a new helper or library — and for duplicate *statements* before proposing to move or create a document. Enumerate what already says the facts it will carry, not only what links to it: a document moved while its restatement stays behind leaves two owners of one fact.
- Distinguish verified facts, inferences, assumptions, and unknowns.
- For a bug, identify the smallest regression test that would fail for the real defect. Prefer real production-shaped data or existing fixtures; otherwise specify the closest representative synthetic data and why it is faithful.

### 3. Choose the smallest sound design — KISS first

Before comparing options, run the KISS gate; it comes before keeping or extending anything that exists:

- **Start from the need, not from the existing mechanism.** State the operator-visible outcome in one sentence, then ask: which component already owns the lifecycle and the data for it? The simplest design usually lets that owner produce the artifact directly (a scheduled job writes the file; the platform's own scheduler fires the task) rather than adding a process that waits to be told.
- **Count moving parts per option** — services, processes, ports, protocols, callbacks, health checks, credentials, network rules, lifecycles, tests that only test the machinery. Prefer the option with the fewest; list what each option adds AND what it lets you delete.
- **Existing machinery is not a requirement.** A mechanism that exists (server, callback, cache, watcher) may only be retained if a concrete, stated requirement cannot be met without it; "it's already there" and "it's well tested" are not requirements. Apply the reliability guard from the shared principles to understand why it exists, then decide whether the need itself disappears under the simpler owner.
- **Name the one thing the simpler design gives up** (e.g. instant push vs. F5/next write) and ask whether anyone actually needs it. If unsure, pick the simpler design and record the dropped capability as a non-goal, not as a deferred feature.
- Write the chosen design so a reviewer can see the gate was applied: a short "premise / KISS" paragraph in the todo that names the owner, the parts removed, and the capability knowingly dropped.

Then:

- Compare only materially viable options.
- Recommend the smallest change that preserves existing contracts and reliability guarantees.
- Prefer clean integration through existing boundaries over a parallel mechanism.
- Propose a new shared abstraction only when there is demonstrated reuse, consistency, or invariant-enforcement value.
- Reject unnecessary indirection, speculative extensibility, unrelated cleanup, and duplicated sources of truth.

### 4. Write one implementation todo

Use the path supplied by the operator. Otherwise follow the repository's todo convention, including `todo/README.md`, applicable `AGENTS.md`, or an equivalent when present. Only when no repository convention exists, use `todo/YYYY-MM-DD_HHMM-<concise-change-name>.md`, where the prefix is the todo's creation date and time so files sort chronologically; never update the prefix afterwards.

Use [references/todo-template.md](references/todo-template.md) as the structure. Adapt headings only when the repository has a stronger established convention, while preserving the same information.

The todo must:

- be self-contained enough for a fresh agent to implement without chat history;
- link to exact stable docs, code, tests, logs, and commands rather than copying large bodies of existing information;
- state accepted architecture and invariants explicitly;
- carry the `## Authority register` from step 0, with `D<n>`/`Q<n>`/`A<n>` cited rather than restated elsewhere;
- define ordered implementation tasks and exact verification evidence;
- identify documentation impact and the existing or proposed stable owner;
- contain no unsupported claims and no premature implementation details that depend on unverified code;
- remain marked `REVIEW REQUIRED` until the user approves it.

### 5. Report and stop

Report:

- todo path;
- concise verified findings;
- recommended direction and why;
- open blocking `Q<n>` gates, stated as questions for the operator;
- material risks or unresolved blockers;
- commands or tests run and their results.

Do not start implementation, even when the direction appears obvious.
