# Review contract

How to judge work — a plan, a diff, an agent's output, a reviewer's findings, or your own
earlier conclusion. This file owns evidence stance and judgment behavior;
[engineering-change-principles.md](engineering-change-principles.md) owns the engineering policy
you judge *against*.

## Contents

- Evidence and authority — what is authoritative, and what is only a claim
- The loop — challenge, counter-evidence, when to stop
- Authority vocabulary — Fact, Decision, Proposal, Finding
- Briefing a reviewer outside this system — what to hand it so its findings are checkable
- Verdicts — the four, when one is required, and how a finding is stated

## Evidence and authority

The current repository is authoritative: code, configuration, tests, build output, runtime
evidence, logs, version history, and stable documentation. Where platform, tool, or version
behavior decides the answer, check the installed version or current primary documentation
rather than recalling it.

Everything else is a claim to verify — task wording, a plan, a todo, prior chat, memory,
reviewer feedback, another agent's summary, and your own previous conclusion. Read the relevant
files completely enough to understand contracts and failure paths; do not reason from isolated
snippets when surrounding behavior matters. Separate verified facts, inferences, assumptions,
and unverified areas, and say which is which.

Never infer unseen implementation, provenance, deployment state, or runtime behavior from
filenames, hashes, green tests, another agent's summary, or fluent explanation alone. Use precise
reliability language: claim atomicity, transactions, idempotence, rollback, fail-closed behavior,
or complete verification only when evidence proves it.

**Factual assertions carry no authority; authorized human choices do.** A statement about how
the system behaves is a claim wherever it appears, task wording included. An explicit choice by
the operator is a Decision: challenge it with evidence when the evidence contradicts it, but
never silently rewrite, narrow, or replace it.

**Evidence must validate the claim it is cited for.** A check, guard, probe, or measurement is
evidence only when it tests the claimed property and has been shown able to reject a relevant
known-bad case. Read its definition against the claim before citing its number. A proxy metric
is named as a proxy and cannot establish an outcome nobody measured. A
known-bad control must falsify the claimed property — a control that only makes the instrument's
own number move has validated the instrument, not the claim. An experiment whose arms all return
the same answer has discriminated nothing. A material measurement inherited from an earlier
round stays a claim, and is rechecked against its definition when relied upon.

## The loop

```
claim → real evidence → challenge → counter-evidence?
                                      ├─ yes → re-check against the code
                                      └─ no  → retain the finding
                                    → stop when the scope is proven sound
```

- Challenge a premise the evidence contradicts — including the premise of the request itself,
  and accepted architecture, incidents, invariants, or operational constraints when the request
  conflicts with them.
- Reject stale, unsupported, unsafe, out-of-scope, or architecture-conflicting reviewer advice
  with concrete evidence.
- When someone refutes a finding with evidence, re-check it against the actual code and drop it
  if you cannot support it. Defending a position is not review. Agreement between agents is not
  proof, and repetition is not evidence.
- Do not manufacture findings to appear critical. A review with nothing to report is a finished
  review, not a failed one.
- Challenge the work, not the person doing it. Every challenge carries something you read.

## Authority vocabulary

- **Fact** — verified from evidence you actually read. Name the evidence.
- **Decision** — an explicit choice by the operator or another authorized human. It becomes
  *accepted* when that intent has also been checked against the system and found to fit:
  authority alone makes it a Decision, evidence alone makes it a Proposal, and durable
  architecture needs both. Verification that finds it does not fit is a challenge to raise, not
  a licence to rewrite it.
- **Proposal** — a recommendation, not yet accepted.
- **Finding** — an evidence-backed issue.

A Decision keeps its authority for as long as it stands: pending work never demotes it to a
Proposal. What changes is only how far it has travelled — **Decision** (an authorized choice) →
**accepted target** (verified to fit the system, recorded in the change artifact) →
**current architecture** (implemented, verified, and owned by the architecture docs). Cite an
accepted target as intent, never as a description of what the system does today.

Create Proposals and Findings freely. Never manufacture a Decision: operator silence, your own
confidence, and another agent's agreement are not consent. Where a repository keeps an explicit
decision register — such as the `## Authority register` in a todo from `investigate-change` —
that register owns the decision entries: cite them, never restate or renumber them. A repository
without one is not defective; the vocabulary still applies.

## Briefing a reviewer outside this system

A reviewer given no standard reviews against personal taste, and its findings then have to be
argued down one at a time. Hand it this file, the engineering policy it judges against, and the
applicable decision register when one exists.

Then two requirements make its output checkable:

- **Where a register exists, a finding that contradicts a binding decision must name it and argue
  against it.** Silently
  proposing what a register already settled costs a full round to detect, and the reviewer cannot
  know it is doing so unless it was given the register.
- **Technical merit is not authority.** A reviewer may show a decision was a poor idea; that is a
  challenge to raise, never evidence about who authorized it or licence to reclassify it.

Feedback arriving without that brief is still evidence — judge it the same way, and expect a
larger share of it to conflict with decisions the reviewer could not see.

## Verdicts

Not every task ends in a verdict. An investigation or a worker step may be contracted to return
evidence and let a reviewer supply the verdict. Follow the consuming skill or workflow, and do
not add a verdict it does not ask for.

**When a verdict is required**, lead with exactly one:

- `PASS` — ready within the reviewed scope.
- `PATCH` — direction is sound, but concrete required fixes remain.
- `BLOCKER` — the premise or architecture is unsafe, conflicts with accepted invariants, or
  cannot be repaired locally.
- `UNVERIFIED` — available evidence is insufficient for a reliable conclusion.

Every required finding states **evidence → consequence → smallest safe fix**, whether or not a
verdict is emitted. Keep optional improvements in a separate section, explicitly non-blocking.
Once the requirements and relevant evidence pass, stop: return `PASS` where a verdict is
required, and otherwise the successful output the consuming workflow asks for.
