# GenosAI

Portable coding-agent configuration and optional AI product utilities.

| Owner | Responsibility |
|---|---|
| [agents/](agents/README.md) | Shared coding-agent environment |
| [integrations/](integrations/README.md) | Product-specific utilities |
| [tools/](tools/README.md) | Setup, checks and source export |
| [docs/](docs/README.md) | Structure, diagrams and source verification |
| [secrets/](secrets/README.md) | Private AI credential storage |

From Linux or WSL, with Make, Python 3.10+, Bash and Git installed:

```bash
make init
make check
make install
make test
```

Default install wires shared instructions/search on the host only. Choose providers and Windows clients
explicitly with the options shown by `make help`; Pi additionally needs a private connection profile.
`config.local.json` holds ignored personal deltas; [the sparse example](config.local.example.json) enables
no connection. Keep credentials in ignored local storage or their native application stores.
[Project instructions](AGENTS.md) define development commands and acceptance.

Tests additionally require Node on `PATH`; runtime acceptance uses the pinned Pi SDK with Node 22.19+
and synthetic transports. Gitleaks 8.30.1 is required by `make public-check`. Native Codex/Windows
checks report explicit skips when their optional clients are unavailable; those skips do not prove
platform support.

Original code, documentation and skills use the [MIT License](LICENSE).
[Third-party notices](THIRD_PARTY.md) retain the terms for bundled upstream material.
