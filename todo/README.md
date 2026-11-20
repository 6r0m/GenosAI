# Change plans

Open plans for repository changes, one file per change, each recording its own authority and gates.
Plans are work in flight: the durable facts an accepted plan establishes move to the owner it names,
and nothing stable cites a plan.

| Convention | Rule |
|---|---|
| Filename | `YYYY-MM-DD_HHMM-<concise-change-name>.md`, from creation time; the prefix is never renamed |
| Admission | A plan is public source and needs its own entry in [the source disposition manifest](../tools/source-manifest.json) before a commit that includes it succeeds |
| Content | Public, portable information only, per [source preparation](../docs/preparation.md); synthetic fixtures instead of operator data |
