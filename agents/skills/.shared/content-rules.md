# Content rules

What may be written into anything durable — a document, a README, a code comment — and how those
divide the work between them. This file owns **what is said**, for every durable artifact and not
documents alone.

Where a document lives and how it is reached is owned by
[documentation-structure.md](documentation-structure.md); which artifact owns which fact is owned
by [engineering-change-principles.md](engineering-change-principles.md). A code comment is covered
here because it is documentation at the shortest possible distance from the code — the same rules
apply, at a smaller size.

## Current truth only

A **current-state** document states what is true now: architecture, contracts, operations,
READMEs, and the code comments beside them. In those, no change chronology — no changelog, no
dated history entries, no "previously / now", no migration narration, no task progress or status.
The same holds for a comment: no change dates, no ticket or task IDs, no author names, no
"changed from X".

A document whose **purpose** is to record history is not a current-state document and this rule
does not touch it: a changelog, release or migration history, an incident and postmortem record,
and ADR history where the repository uses ADRs that way. Each owns its history by design.

ADRs are the one that depends on the repository. Where accepted ADRs carry current architecture
and rationale rather than a record of what was once decided, they are a current-state owner and
this rule applies to them as one. Read the model the repository actually uses; whichever role it
gives them is the role they keep, and the architecture reference owns when an established system
may be changed at all.

What no historical record may become is a parallel source of truth for current architecture: when
such a record and the current-state document disagree about how the system works now, the
current-state document is the one that describes it.

A date, a version, or a status is welcome when it **is** the current truth — a support cutoff, a
compatibility floor, a deprecation deadline, the state a service is actually in. The test is not
whether a date appears but whether it describes the system now or narrates how it got here.

When a fact changes, **edit it in place**. The diff is the record, and a document that
accumulates is one nobody trusts, because a reader cannot tell which line is still true.

What each kind of truth belongs to:

| what | owner |
|---|---|
| how the system works now | the current-state durable owner |
| general repository evolution | version control |
| the history a record exists to keep | that record — changelog, release or migration history, incident log, ADR history where ADRs are used that way |
| work in flight — steps, progress, blockers, open questions | the transient change artifact |

## Comments and documents divide the work

The document carries the **shape** that
[engineering-change-principles.md](engineering-change-principles.md) assigns to stable
documentation: boundaries, invariants, the why that spans more than one file. The comment carries
the **detail closest to the code**: the local reason this line is as it is.

- A comment is **short and self-contained** — readable without opening anything else.
- It **complements** the document, never repeats it. A fact belonging to both is written once, in
  the document; the comment says only what a reader needs right here.
- Never paste a decision log, a conversation, or a summary of the work into a comment.
- Explain non-obvious intent, constraints, invariants, failure reasoning, or consumers. Do not
  narrate mechanics the code already shows.

When an explanation genuinely outgrows a comment, keep the **essential invariant** in the comment
and link the durable document that owns the rest. A comment that only links has lost the reader
who needed one sentence. What that link must say — enough to decide whether to follow it — is in
[the link rule under Routing](documentation-structure.md).

## The dependency runs one way

A transient change artifact may point at durable documents and code. **Durable documents, source,
comments, tests and configuration must never point back** — not at a todo, plan, chat, or review
artifact, and never at a bare decision ID from one.

Those artifacts are deleted, renamed, and closed; a durable file that depends on one rots when
that happens. If something in a change artifact is worth citing from durable code, it is worth
moving to its durable owner first — then cite that.

One exception: automation whose literal runtime input is a task or checklist file may name it.
That is a runtime dependency, not documentation coupling.
