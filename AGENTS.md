# GenosAI project

GenosAI provides portable AI tooling. `agents/` owns the shared coding-agent
instructions, skills, permissions and native provider integrations. `integrations/` owns product
utilities. Universal behavior lives in [agents/AGENTS.md](agents/AGENTS.md); this file owns project rules.

## Entrypoints

- `make init`: create a missing ignored local example; preserve existing input.
- `make check`: validate source/local metadata without installation, network calls or native writes.
- `make install PROVIDER=shared PLATFORM=host`: default instruction/search wiring only.
- `make install PROVIDER=claude|codex|pi PLATFORM=host|windows|both`: explicitly selected integration.
  Claude changes require its existing reviewed plan; Pi runtime acquisition additionally needs `RUNTIME=1`.
- `make uninstall` accepts the same selection. Foreign/native credentials and unrelated resources survive.
- `make test`: offline tests, including locally available native clients and synthetic provider transports.
- `make public-check`: pinned secret scanner, private-artifact/path checks, and independent Git index/history checks.
- `make export DEST=<outside-source-path> MANIFEST=<receipt.json>`: curated source snapshot without Git/private state.

Run sequential platform acceptance suites: installer fixtures share fixed scratch names.
Use ignored `tmp/` for diagnostics. Optional native runtimes and authenticated/paid evaluations are explicit;
missing required platform coverage is a gap, not release proof. Never run a live account/model to replace
synthetic regression coverage. `secrets/` files are private; inspect references/metadata, not values.

## Ownership and acceptance

[Architecture](docs/architecture/structure.md) owns boundaries; component owners own their schemas,
validators, generated/native projections and failure behavior. Keep one canonical source and each native
writer's approval/version/collision protections. Public defaults must not inherit private machine choices.

Before cutover, verify an independently extracted artifact in synthetic homes with the old source unavailable.
Preserve local input and native foreign state; transfer ownership through existing owners. Public release
also requires license/provenance review, explicit publication authorization and anonymous
acquisition checks. No Git staging, commits, remote writes or live cutover is implicit in preparation work.
