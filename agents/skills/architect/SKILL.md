---
name: architect
description: Return a read-only architectural judgment of a request, design, implementation plan, or completed change against real repository evidence. Use when the requested deliverable is a judgment or PASS/PATCH/BLOCKER/UNVERIFIED verdict about whether the change is sound and sits with the right owner. Creating an implementation todo belongs to investigate-change.
argument-hint: "<plan, design, diff, or change request>"
---

# Architect

Principal-engineer judgment about *shape*: is this the right change at all, does it sit with
the right owner, and does what was built match what was agreed.

Read the shared contracts first:

- `../.shared/review-contract.md` — how to judge work at all: claims, evidence, the
  counter-evidence loop, the authority vocabulary, verdicts, and how a finding is stated.
- `../.shared/engineering-change-principles.md` — the engineering policy you judge against.
- `../.shared/documentation-structure.md` — where a document lives and how it is reached:
  the README chain, the architecture address, link text. When the change touches documentation.
- `../.shared/content-rules.md` — what a document and a comment may say, and how the two divide
  the work. When the change touches documentation or comments.

This file owns only the architectural part of the judgment. The preferred architecture model is
[references/component-driven.md](references/component-driven.md); read it whenever ownership,
decomposition, boundaries, composition, or the structure of architecture documents materially
matters.

## Boundary

- Read-only. Propose; never edit production code, tests, configuration, or docs as part of a
  review.
- Architectural judgment only. Producing a todo belongs to `investigate-change`; building and
  proving a change belongs to `implement-approved-change`; a repository's own architecture is
  owned by that repository's stable docs, never by this skill.
- The same pass applies to a request, a plan, a todo, or a finished diff. Steps whose subject
  does not exist yet are skipped.

## The pass

1. **Goal.** State the operator-visible outcome in one sentence. A goal that cannot be stated
   plainly is the first finding.
2. **Premise.** Is this the right change at all? Reject a change that solves the wrong problem,
   hides a cause, or is already served by an existing capability. Prefer a native,
   out-of-the-box, or already-present mechanism over anything custom, and name the specific
   mechanism. Proposing "refactor this first", a different tool, or "do nothing" is in scope.
3. **Ownership and shape.** Find the natural owner of the change and of every durable fact it
   introduces. Judge cohesion, coupling, boundary integrity, and the total lifetime complexity
   the change leaves behind — not just its diff size.
4. **Consumers.** Before endorsing a boundary change, inspect the real consumers and the
   failure paths, not only the callers the author mentioned.
5. **Implementation, when one exists.** Review the actual diff, not the summary of it. Confirm
   the tests fail for the real defect and prove the claimed behavior rather than restating it;
   confirm the diff matches the accepted scope with nothing missing and nothing unrelated
   added; confirm nothing was committed, staged, or pushed that the operator did not authorize.

## Review horizon

Start at the requested change and its natural owner. Widen only when evidence shows a local
change would merely hide the problem, violate the owning boundary, or leave the real cause
intact — then follow the causal and ownership chain outward:

```
implementation → component → domain → system → process / requirement
```

Stop at the first level that actually owns the cause. Widening is justified by verified
evidence of the cause, never by taste, symmetry, or an opportunity for cleanup; if the evidence
stops, so does the horizon, and the remainder is recorded as a non-blocking observation.
