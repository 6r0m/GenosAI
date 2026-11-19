# Documentation structure

How documents and references are shaped and reached, so a human or an agent finds the right one
fast. This file owns **shape and navigation only**. Which document owns which fact is owned by
[engineering-change-principles.md](engineering-change-principles.md); the architecture model a
repository follows is owned by the consuming skill's own architecture reference.

## Contents

- Routing — the README chain, and the one-route rule
- Length — when to add contents, when to decompose
- Where architecture lives — the fixed `docs/architecture/` address
- `structure.md` — the required architecture document
- Diagrams — their own directory, its router, and `main.md`
- `docs/pitfalls.md` — optional diagnostic entries
- Agent-facing references — reference depth

## Routing

**What it is for.** One entry point, and from it any fact in the repository at whatever depth it
lives — without knowing the tree first. A reader walks only the branch that holds their answer, so
each hop narrows what they are paying attention to and the context a question costs stays
proportional to the question rather than to the repository. **That chain is the index**: a table
of contents that spans modules instead of pages, and the reason an agent can work in a large
repository without loading it.

**How it works.** The `README.md` at the repository root routes to the top-level owners. Each of
those routes to its own children, and so on down: **every separation-of-concern directory carries
a `README.md` that links to what is inside it**, so an agent reaches any single file by routing
without having to search.

A hop moves exactly one level. A component routes to its `docs/`, which routes to
`architecture/`, which routes to `structure.md` and to `diagrams/` — never straight past a
directory to something nested inside it. Skipping a level saves one read and costs the reader the
level that gave the target its meaning.

Ownership depth is not reference depth. Walking root → subsystem → component is the point;
nesting one supporting file behind another is not (see Agent-facing references).

An **owner** is a directory that holds a responsibility of its own; its `README.md` is how that
ownership is declared and reached, not what creates it. So the README is the marker a reader and
a checker can both see — vendored, generated, and third-party trees are not owners even when they
carry one, and a directory with a real boundary that lacks a README is an owner missing its front
door, not a non-owner. The directories that do carry one are the layout's **router nodes** — the
half a checker can see. A tool may prove every router node is reachable; it can never prove every
real owner was found, and must not claim to. A **route** is a link from a
router to something inside its own directory; a link pointing anywhere else is a **citation**,
whatever file it sits in.

**A README is a router.** One sentence saying what this directory owns, then one row per child.
Nothing a reader needs after the first minute lives in it — that belongs to the document that
owns it, reached by a link. The single bounded exception is an owner's own README, which may also
say how to run the thing and where the entry point is, because a reader needs that before any
amount of routing helps; once it outgrows a line or two it has its own owner and gets a row like
everything else. A README that explains a boundary, an invariant, or a decision has stopped
routing and become a second architecture document.

The chain holds only while every link in it stays a router:

- **One entry per child: one line, one link, a few words saying what is behind it** — enough to
  choose, never enough to answer. The words say what the target *owns*, not what it *says*. The
  moment an entry summarises the target's content, that content has two homes and they drift.
- **Exactly one route to each owner** — its own parent's. A second route is a second thing to
  update when the child moves, and the two will disagree.
- **Route to the owner, not past it.** Linking a grandchild from the root skips the level that
  gives it context and leaves the intermediate router looking complete when it is not.
- **Every owner appears in its parent's router.** A directory nothing routes to is unreachable by
  traversal, whatever else happens to point at it.

### What a link says

A reader follows a link to answer a question, and must be able to decide **whether to follow it
without following it**. So the link text, together with the words immediately around it, answers
one question: *what will I find there?*

- **The link text plus its immediate context must make clear what is on the other side.** Prefer
  descriptive text, most distinguishing words first. A filename-only link is acceptable when its
  immediate context already provides that description ("… is owned by `review-contract.md`").
- Text and target must agree: text that names a directory must not point at one file inside it.
- Never use the same text for two different targets in one document.

Citations are unrestricted: a sibling README pointing at the document that owns a fact is
exactly right. What stays unique is the **route**, not every mention — so when a source of truth
changes, one document changes and the rest already pointed at it. A fact that is hard to find is
a routing problem, never a reason to copy it to a second place.

## Length

Length is a navigation signal, not a failure condition:

| signal | response |
|---|---|
| over ~100 lines | add a compact `## Contents` near the top, when selective reading is useful |
| several independently useful concerns, or so large that every reader pays for all of it | decomposition review: split by concern, keep the owner |

A table of contents is not a licence to keep growing. Splitting by line count is not a fix
either — `part-2.md` has no owner and no meaning. Split where a concern ends.

The 500-line budget belongs to `SKILL.md`, whose whole body loads at once. It is not a general
document limit.

## Where architecture lives

Every architecture-owning scope — project, domain, component — uses the same address, so an
agent routes to it without looking:

```
<owner>/
├── README.md                  routes to docs/
└── docs/
    ├── README.md              routes to architecture/ and to anything else durable here
    ├── architecture/
    │   ├── README.md          architecture router only
    │   ├── structure.md       required
    │   ├── <concern>.md       only from a real separation of concerns
    │   └── diagrams/          every view, never prose
    │       ├── README.md      routes to the views
    │       ├── main.md        required
    │       └── <concern>.md   one perspective, named for the concern it serves
    └── pitfalls.md            optional
```

The directory exists from the first day. That is the point: architecture grows, and the route
must not change when it does.

This layout is the **preferred default** — for new architecture, and for cleanup an architect has
evidence for. A repository whose own convention is coherent and genuinely owned keeps it; migrate
only on evidence of drift, duplicated authority, or an owner nobody can name.

Each required file above has a fill-in template beside this file, starting with
[the owner README, one row per child plus what a reader needs in the first minute](templates/owner-readme.md): copy it,
delete its leading comment, fill it in. A `<concern>.md` follows the shape of whichever file it
was split out of.

## `structure.md`

The one required architecture document: this owner's structural truth at its own level — what it
is for, its boundaries, its parts as black boxes each linked to its own architecture, its
invariants and its decisions. It never draws or restates the relationship graph at this level:
`diagrams/main.md` states that graph, and `structure.md` cites it. Copy
[the structure template, whose sections are purpose, boundaries, composition, relationships,
invariants and accepted decisions](templates/architecture-structure.md) and fill it in.

Drop a section that has nothing true to say; never fill one with "N/A". What may go inside a
section — current truth, and why a changelog or a status line is never it — is in
[content-rules.md](content-rules.md).

An owner grows by moving a concern *out* of `structure.md` into its own `<concern>.md` — named
for the concern, never for symmetry, and never for a document type. Runtime behavior is one such
concern: give it a file only when a specific interaction is architecturally important or
surprising. Deployment likewise, only where infrastructure materially shapes the architecture.
There is no generic `runtime.md` or `deployment.md`.

## Diagrams

`docs/architecture/diagrams/` holds every view of this owner, and it exists from the same first
day as the rest of the address. Views are their own separation of concern: they are read
differently, they go stale differently, and mixing them into prose is what makes an owner's
architecture page something an agent has to scan instead of route through.

`main.md` is **required**, and it is the one statement of this owner's relationships at its own
level: its immediate parts and the external participants it relates to, as black boxes, each
relationship named by the contract it goes through. Nothing else draws or restates that graph. It
holds no signatures, fields or payloads — the contract owns those — and nothing inside a part,
which that part's own `main.md` draws. A view that spans several levels is generated from their
owners, never drawn by hand. [Code still owns executable behavior](engineering-change-principles.md):
a view that disagrees with the code is stale, not authoritative.

Each further file is one perspective named for the concern it serves, never for a diagram type,
and states only that concern. Copy
[the diagrams router, a table of one row per view](templates/diagrams-readme.md) and
[the main view, this owner's relationships at its own level](templates/diagrams-main.md).

The directory's `README.md` routes to the views and `architecture/README.md` routes to the
directory — the same one-level hop the chain uses everywhere, not a special case for pictures. A
link from `structure.md` to a view is a **citation**, not a route: put it beside the prose that
relies on it.

## `docs/pitfalls.md`

Optional, and not architecture. Worth keeping when an owner has recurring, non-obvious traps
that cost real diagnosis time. Copy [the pitfalls template, one entry of symptom, root cause,
fix, where, and what test now catches it](templates/pitfalls.md).

It is not an append-only history of mistakes. An entry survives only while it still helps
prevent or diagnose a realistic recurrence; once a regression test and an invariant make the
story unnecessary, prune it.

## Agent-facing references

- Keep references **one level deep** from the file that consumes them. An agent may preview a
  nested file with a partial read and silently miss what it never saw.
- Link directly from the consuming skill or router to each file it needs, not through an index.
