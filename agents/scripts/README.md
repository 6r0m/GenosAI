# Agent lifecycle interfaces

| interface | operation |
|---|---|
| [install.sh](install.sh) | install selected or all configured providers |
| [uninstall.sh](uninstall.sh) | uninstall selected or all configured providers |

Both interfaces delegate to [the shared lifecycle owner](../lifecycle/README.md).
`install.sh --approve <plan id>` applies a Claude settings plan that was approved outside a terminal;
[the Claude Code provider](../providers/claude/README.md) owns that plan.
Provider and connection selection belong to its single configuration registry; provider-specific
behavior belongs to [the provider owner](../providers/README.md).
