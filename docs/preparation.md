# Source preparation and release

`make check` validates source syntax and local metadata. `make test` exercises the component contracts
without real provider traffic. `make public-check` requires Gitleaks 8.30.1: it proves a synthetic secret
is detected, scans a source-only working snapshot, and rejects personal-path candidates. In an independent
Git repository it also scans the staged snapshot and distributed history; ancestor repositories
are excluded. It never prints matched secret values.

The reviewed [source disposition manifest](../tools/source-manifest.json) is the public-file allowlist,
including itself, reusable defaults, synthetic fixtures and required upstream notices. A path admits
exactly that file; a path with a trailing separator (`todo/`) declares a reviewed directory scope that
admits every portable, nonprivate descendant and nothing beside it, including `todo/done/`. Everywhere else a new
file requires explicit review and admission, even inside an existing component. Scope admission never
overrides private disposition, a name a target platform cannot represent refuses the check, and two paths
differing only by case refuse rather than overwriting each other; a declared scope absent from the checked
tree fails closed rather than protecting nothing. Missing admitted files, unknown nonprivate files, private
entries in the manifest and source links fail closed before export creates a destination.
Artifact checking also refuses empty directories outside the admitted tree.
Do not regenerate admission from a directory walk or the Git index as part of export/check: a scope is a
reviewed declaration, not a walk.

Private disposition remains exclusion: local settings, credentials, caches, logs, backups, native stores
and Git metadata stay with their private owners and are skipped before opening them. No enclosing Git history
or historical execution receipt is distributed. Pattern scans cannot certify arbitrary personal data in an
admitted file; review changes to admitted content as well as the admission list.

`make export DEST=<outside-source-path> MANIFEST=<receipt.json>` produces a source-only directory and
hash receipt. The output receipt identifies copied bytes; it does not authorize file admission. Export never
copies private input. Verify the exported directory with its own tools, then archive/extract it independently and
repeat check/test/setup using synthetic homes. `python3 tools/release.py check <artifact> --artifact`
refuses any private or unadmitted artifact instead of silently excluding it. A nonempty independent Git index
must contain a complete admitted snapshot with its own manifest; index names are checked before content access.

On Linux/WSL, normalize archive ownership and timestamps instead of embedding the packaging host's
user/group identity:

```bash
tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -C <source-export> -cf <source.tar> .
```

Inspect archive headers as well as extracted content. Directory/content scanners cannot prove that
an archive's ownership names or metadata are private-data-free. The CI rehearsal uses the same normalized route.

The root `.gitattributes` keeps source LF and pinned vendor bytes stable independently of the enclosing
repository, including checkout with automatic Windows line-ending conversion.

Git ignore behavior alone is insufficient: a force-added key is still tracked. The public check inspects
staged filenames before accessing staged content. `make init` or `make hooks` registers the local [Git gates](../.githooks/README.md).
Pre-commit checks the complete staged snapshot using its own staged manifest; working edits
do not substitute for staged bytes. Pre-push also scans working source and all Git refs.
Missing tools refuse. Existing foreign hooks remain intact and require explicit integration.
Run `make public-check` before each authorized push. Synthetic controls must distinguish detection from an
unavailable/broken scanner. Human review owns names, email attribution, URLs, source topology and proposed
Git identities that pattern matching cannot judge.

Source distributions retain applicable project and third-party license terms; vendored notices must survive
export. A passing preparation check does not create a repository, transfer live ownership, authorize
publication or prove public access. Publication requires separate authorization and anonymous acquisition
and setup checks against the reviewed artifact.
