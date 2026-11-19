---
name: implement-approved-change
description: "Implement an approved todo: regression-first proof for bugs, the smallest architecture-aligned change, full verification, durable knowledge migrated to stable docs. Use only when the user explicitly asks to implement an approved plan or todo."
argument-hint: "<approved todo path>"
---

# Implement approved change

Implement the explicitly approved todo, prove the behavior, and leave durable knowledge in its proper stable owner. Do not treat the todo's existence as approval.

Read these before proceeding — the first two on every run, the last two when the change touches
documentation or code comments:

| what you will find | file |
|---|---|
| the engineering policy: KISS/SOLID/YAGNI, the reliability guard, one owner per durable fact | `../.shared/engineering-change-principles.md` |
| how work is judged: evidence stance, the counter-evidence loop, the authority vocabulary, verdicts | `../.shared/review-contract.md` |
| where a document lives and how it is reached: the README chain, the architecture address, link text | `../.shared/documentation-structure.md` |
| what a document and a comment may say, and how the two divide the work | `../.shared/content-rules.md` |

## Preconditions and authority

1. Read applicable `AGENTS.md`, `CLAUDE.md`, nested repository guidance, the approved todo, every stable document it references, and the relevant implementation and tests.
2. Confirm the current repository still matches the todo's verified evidence and assumptions.
3. Inspect current working-tree changes and preserve unrelated user work.
4. Do not stage, commit, push, reset, or discard changes unless the user explicitly requests it.
5. Never follow the todo blindly. Repository evidence and accepted stable contracts remain authoritative.
6. Read the todo's `## Authority register` when present. Binding `D<n>` entries constrain the approved implementation and outrank reviewer findings, agent preference, and the todo's derived `## Decision` within their stated scope. Never treat an `A<n>` assumption as operator authority. Do not cross an open blocking `Q<n>` gate; continue independent authorized work when it is safe, and return `BLOCKER` only when the unresolved gate prevents further valid progress or completion.

When the current repository invalidates a material decision, scope boundary, invariant, or acceptance criterion, do not silently redesign it. Return `BLOCKER` or `PATCH` with evidence and the smallest required plan correction. Local implementation details may adapt when they preserve the approved intent and guarantees.

## Workflow

### 1. Establish baseline

- Identify affected boundaries, owners, failure paths, and existing reusable components.
- Run the narrow relevant baseline tests when practical.
- Record exact commands and outcomes.
- State the target separation of concerns, acceptance criteria, operator approval boundaries, and expensive gates before implementation.

### 1.1 Keep execution inside the approved scope

- Treat a requested operator review before promotion, publication, deployment, or durable authority mutation as a hard stop. Produce only isolated or reversibly restored candidate state, inspect that exact candidate, report the requested evidence, and wait for approval.
- Use focused, static, unit, and narrow integration evidence as the debugging loop. Run broad suites, Matrix jobs, packaging, and equivalent expensive workflows only as acceptance gates at a coherent boundary.
- Preflight selected profiles, fixtures, counts, schemas, and contract compatibility with the cheapest available checks before the first expensive gate.
- When dependencies permit, run the target acceptance path before regression envelopes. A regression envelope is not another implementation workstream.
- Default to one initial attempt plus one replacement after a necessary fix for each expensive gate. On a further failure, stop with evidence and request a scope decision unless repository rules or the operator explicitly authorize more attempts.
- Fix an adjacent failure only when the current change caused a supported-contract regression or the approved final acceptance requires it. Record unrelated stale fixtures, migrations, cleanup, refactors, and compatibility work separately instead of absorbing them.
- Required stable contract documentation is part of the change. Unrelated documentation polishing is not.
- Observe long jobs at meaningful stage boundaries. Do not fill the transcript with fixed-interval polling or repeated unchanged log tails.

### 2. Create proof before the fix

For a bug:

1. Add the smallest regression test that exposes the real defect.
2. Prefer captured, sanitized, or existing production-shaped data and fixtures.
3. When real data is unavailable, synthesize the closest representative input and document why it preserves the triggering properties.
4. Run the exact new test before modifying production behavior.
5. Confirm it fails for the expected reason. A compilation error, invalid fixture, unrelated exception, or incorrect assertion is not valid red evidence.
6. If no faithful deterministic reproduction is possible, do not create a misleading synthetic test. Record why, use the strongest available runtime or operational evidence, and return `UNVERIFIED` unless the fix can be proven adequately.

For a feature:

- Add executable acceptance evidence first where practical.

For a refactor with intentionally unchanged behavior:

- Establish characterization tests or equivalent existing coverage before structural changes when regression risk warrants it.

### 3. Implement the smallest safe change

- Integrate through existing architecture, domain boundaries, extension points, configuration, errors, and lifecycle mechanisms.
- Reuse existing helpers and libraries when their contracts fit.
- Create or extend a shared component only when it has a clear owner and demonstrated reuse, consistency, or invariant-enforcement benefit.
- Apply SOLID to responsibilities and contracts without creating speculative layers.
- Preserve compatibility and proven reliability guarantees.
- Avoid unrelated cleanup, broad rewrites, parallel mechanisms, duplicate state, hidden fallback behavior, and new dependencies without concrete need.
- Keep failure handling explicit and observable.

### 4. Prove green

1. Run the exact regression or acceptance command used for red evidence and confirm it now passes.
2. Run the relevant verification matrix from the todo: targeted unit tests, integration tests, smoke tests, static analysis, build checks, and runtime verification as applicable.
3. Test important failure paths, not only the successful path.
4. Use runtime or log evidence when tests cannot fully demonstrate the operational behavior.
5. Report exact commands, counts or outcomes, and failures. Never claim checks were run when they were not.

### 5. Migrate durable knowledge correctly

- Review the todo's documentation plan against the final implementation.
- Update the existing stable document that owns the concern.
- Create a new stable document only when no suitable owner exists and the durable content justifies it.
- Organize or update the nearest README/table of contents by separation of concerns so future agents can find the owner quickly.
- Keep one source of truth. Replace duplicated explanations with links to the authoritative stable owner.
- Write the migrated content to the rules in `../.shared/content-rules.md`, which owns what a durable document and a code comment may say and the one-way dependency on this todo.

### 6. Final integration review

Review the complete diff against:

- the approved goal, scope, decision, and invariants;
- current repository architecture and stable sources of truth;
- regression evidence and failure paths;
- KISS, SOLID, and YAGNI;
- duplicate logic, duplicate documentation, and unnecessary abstraction;
- unrelated edits and accidental generated artifacts;
- documentation ownership and router consistency.

Update the transient todo with task status and exact verification evidence when that is the repository convention, but do not make any durable artifact depend on it.

## Final report

Start with one verdict: `PASS`, `PATCH`, `BLOCKER`, or `UNVERIFIED`.

Then report concisely:

- implemented behavior and integration point;
- red test and its expected pre-fix failure;
- green verification commands and results;
- stable documentation updated or the explicit reason none was needed;
- required remaining findings, each with evidence, consequence, and smallest safe fix;
- optional improvements separately and only when genuinely useful.

Return `PASS` and stop once the approved requirements and relevant evidence are satisfied.
