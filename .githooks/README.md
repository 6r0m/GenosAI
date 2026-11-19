# Local release gates

`make init` (or `make hooks`) registers this directory in this repository's local
Git configuration. Existing foreign hook configuration or active hooks cause a
refusal; integrate them deliberately instead of silently disabling them.
Source archives without their own Git repository skip registration.

- `pre-commit` checks the complete staged snapshot against its own reviewed source
  manifest, private-file rules, personal-path candidates and Gitleaks 8.30.1.
- `pre-push` reuses the working-source, index and all-ref Git-history checks.

Both delegate to [the release checker](../tools/release.py) through the shared
interpreter resolver in strict mode. Missing tools or failed checks block the
operation. Neither hook stages, edits, commits or pushes source. Diagnostics stay
under ignored `tmp/`; matched secret values are redacted.

Git hooks are local convenience checks and can be bypassed. The independent
[CI workflow](../.github/workflows/verify.yml) repeats release checks. Human review
still owns arbitrary personal content, archive metadata and commit identities.
