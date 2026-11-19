# GenosAI structure

## Purpose

Provide a reusable coding-agent environment and optional AI application utilities, with independent
setup, verification and source distribution.

## Owns

The source layout, root command entrypoints, composition of maintained components, and separation
of distributable source from workstation and runtime data.

## Does not own

Run orchestration, model-serving applications, downloaded model weights and credentials for unrelated
tools remain outside this project's maintained source. Native applications own sign-in credentials
and settings outside the managed integration contract.

## Composition

| Component | Responsibility |
|---|---|
| [Agents](../../agents/README.md) | Shared coding-agent instructions, skills, permissions and native integrations |
| [Integrations](../../integrations/README.md) | Optional product-specific utilities |
| [Tools](../../tools/README.md) | Local initialization, verification and source distribution |

[Credential storage guidance](../../secrets/README.md) owns the AI-local storage boundary;
credential files are user data and may live in a configured external directory.

## Relationships

The component and external-data relationships are drawn in [the main view](diagrams/main.md).

## Invariants

The checkout operates independently of any enclosing repository or its Git history. There is one
canonical implementation of each maintained component.

Tracked source contains reusable defaults, synthetic examples and required notices. Workstation
preferences, credentials, runtime caches, downloaded assets, logs and backups remain outside distribution.

Default installation selects the shared environment on the host. Provider and Windows-client changes
require explicit selection. Initialization preserves existing local input; checks make no provider
request or native settings change. Component owners retain their validation and mutation contracts.

Distribution requires reviewed file admission. Secret-pattern checks cannot certify absence of arbitrary
personal prose or topology; manual content and metadata review remains necessary.
