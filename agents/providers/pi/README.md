# Pi provider

[lifecycle.sh](lifecycle.sh) installs or removes the selected Pi integration. It is dispatched through
[the shared lifecycle interfaces](../../lifecycle/README.md) and reads their single configuration owner.

| boundary | owns |
|---|---|
| [Runtime](runtime/README.md) | managed launch and native configuration projection |
| [Permissions](permissions/README.md) | adapter, Pi rule entry and shared guard reuse |

[The local package manifest](../../package.json) registers this provider's extension and the canonical
skills. [Provider tests](../../tests/providers/README.md) own deterministic and installed-route proof.

Installation validates the connection, credential reference and existing projections before creating
wiring or registering the local package. An existing runtime supplies catalog and installed-version
validation before acquisition; a missing runtime is acquired from the checked-in install lock with
`npm ci` only after the available checks pass, then its catalog is validated before wiring. If that
validation fails, only the newly owned runtime tree and owner marker are removed; pre-existing owned
runtimes and foreign prefix files survive. Runtime acquisition or cleanup failures are reported. This is
a preflight boundary, not an atomic two-platform transaction.
