<!-- Template for <owner>/docs/architecture/structure.md. Copy the file, delete this comment.
Sections in order: Purpose / Owns / Does not own / Composition / Relationships / Invariants /
Accepted decisions / Risks and technical debt.
Drop a section with nothing true to say; never fill one with "N/A". Adapt headings only where the
repository has a stronger established convention, preserving the same information.
The relationship graph at this level is diagrams/main.md: cite it, and never redraw or restate it in
any section here — not as an arrow, and not as a sentence saying who depends on whom.
Which relationships this scope owns is decided by the shared engineering-change-principles.md. -->

# Structure

## Purpose

What this owner exists to do, in one or two sentences.

## Owns

The responsibilities that belong to this owner and to nobody else.

## Does not own

The responsibilities a reader would plausibly expect here, and where they actually live. Write
this even when it feels obvious — it is what prevents boundary drift.

## Composition

The children or internal parts, each as a black box: name, one-line responsibility, and a link to
its own architecture when it has one. Never restate their internals.

## Relationships

This owner's relationships are drawn once, in [the main view](diagrams/main.md); do not restate
that graph here. For a relationship that needs it, say why it exists and what it constrains, and
refer to it only by the contract it goes through — "Through `<contract>`:" — never by who depends
on whom.

For a relationship owned elsewhere, cite its canonical owner and state here only consequences this
owner itself owns, such as "retries a failed <contract> call once".

## Invariants

What must stay true for this structure to hold, stated so a reviewer can check it.

## Accepted decisions

An **index only**, so a reader can find them; it owns no rationale of its own. Each accepted
decision is written beside the boundary, dependency or invariant it constrains, in the section
above that already describes it:

```md
## Relationships

Through `<contract>`: nothing flows back.

**Decision:** <the explicit human choice>
**Why:** <the constraint or property that made it right>
```

A decision is an explicit human choice that was then verified to fit this system: an agent's
preference is not a decision, and an unverified intent is not yet accepted. Keeping the rationale
with the fact is what stops the two drifting apart.

- <decision title> — see [Relationships](#relationships)

## Risks and technical debt

Identified risks and known debt, highest cost first. A risk is something already spotted that
could bite — it does not have to have bitten yet; debt is what this owner knowingly does not
handle today. One entry each: what it is, what it costs when it lands, and the measure that would
mitigate or remove it when one is known.

What does not belong here is a question nobody has answered — "should this move to Redis?" is a
decision not yet taken, and pending work lives in the change artifact or the backlog, not in the
document that states current truth. A risk is a property of the system you can already name; a
question is work you have not done.
