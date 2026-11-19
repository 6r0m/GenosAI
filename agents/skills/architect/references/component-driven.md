# Component-driven architecture — the preferred default

The default model to reach for when deciding **where something belongs**. It is a
design preference, not a migration mandate: a repository with a coherent ADR, spec, or
rules system is not defective for using it. Preserve what works and change it only on
evidence of a real problem — drift, duplicated authority, harmful indirection, or an
owner nobody can name.

## Owners

- A **domain, component, module, or plugin** is the natural unit of architecture — not
  a technical layer invented for symmetry.
- Each is a **black box** with an explicit responsibility and an explicit
  non-responsibility. Writing down what a component does *not* own prevents most
  boundary drift.
- Aim for high cohesion inside a component and minimal coupling across the boundary.
  Couple to a contract, never to a neighbor's internals.

## Where truth lives

Which artifact owns which kind of truth, and which owner a fact or a relationship between owners
belongs to, is the shared engineering policy in `.shared/engineering-change-principles.md`. Where
an owner's architecture documents live and how they are reached is
`.shared/documentation-structure.md`; current truth versus history and work in flight is
`.shared/content-rules.md`.

## History

- Do not grow an ADR, spec, or rule forest by default merely to retain engineering
  history; where history and current truth each belong is `.shared/content-rules.md`.
- When a historical decision still constrains the current design, integrate its durable
  meaning into the proper current architectural owner.
- Where such a system already exists and is coherent, keep it. Migrating it is a change
  that needs its own evidence and its own approval.

## Restraint

- Every abstraction, layer, and component costs maintenance and reader context forever.
  Each must justify that cost with a present need.
- Do not create a component or layer for conceptual symmetry, for a hypothetical future
  consumer, or because a sibling has one.
- Prefer extending an existing architectural owner over introducing a parallel component
  for the same responsibility.
