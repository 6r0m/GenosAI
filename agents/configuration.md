# Local agent configuration

[config.py](config.py) owns loading the AI checkout's ignored `config.local.jsonc` and validating
its shared structure. Component defaults stay with their current owners. Start from the
[commented example](../config.local.example.jsonc); do not copy an entire provider configuration.
Local input contains preferences and references only. Credential files stay in ignored AI-local storage or an explicitly configured external directory; native sign-ins stay native.

## Composition

An absent local file means no private additions. Invalid JSON, duplicate/unknown shared fields,
unreadable input, invalid shared types, or overly broad/protected additional roots refuse rather than selecting defaults.
Each provider validates its own overrides before application.
Errors identify the invalid contract without printing local values. A broken link is unreadable input.

The `permissions.extra_write_roots` additions belong to the shared file-edit guard. They must be
absolute paths in a supported native, WSL, or Git Bash spelling. The guard resolves them through its
existing path owner before comparing targets. No directory is created. Home/profile roots, drive
roots, and Claude policy directories cannot be sanctioned as scratch. The current home directory's
Claude project state and the platform's temporary areas are derived, not copied from another user.
Cross-platform or additional repository roots require an explicit local addition.

The `claude` object adds to [Claude's component defaults](providers/claude/README.md). Known object
keys merge recursively; scalar values override with the same JSON type. Permission `allow`, `deny`,
and `ask` arrays append unique rules. Other arrays replace. Unknown owned fields, hook replacement,
and overrides that break the required guard posture refuse. Unowned native settings remain native
settings; the local file does not turn them into managed keys.

For example, a sparse local addition can protect one more project directory:

```json
{
  "claude": {
    "permissions": {
      "deny": ["Read(./private-notes/**)"]
    }
  }
}
```

Browser integration remains optional and is described by the
[browser skill's setup owner](skills/drive-browser/references/local-setup.md).

## Validation and application

From the AI checkout root, these commands read source/local metadata without changing native settings
or starting a model, browser, or service:

```bash
python3 agents/config.py
python3 agents/providers/claude/settings.py validate
```

Installation validates shared input and the selected provider's preflight before creating links.
Removal remains available when local input is broken. Pi then accepts only its canonical source-root ownership; an older projection that needs a migration ownership reference safely refuses until that metadata is repaired. File-edit guards read local roots on
each relevant call; malformed input returns a deny through the ordinary wrapper. Unexpected runtime
failures retain the [permission owner's documented behavior](permissions/README.md).

Claude settings change only through the existing approved-plan writer. Its approval binds the public
defaults, local bytes, canonical source location, projection code, generated commands, and each native
file's bytes/path. Changing a local value invalidates an earlier approval. The session warning uses
the same composition and generated paths. The writer never rewrites the local file.

## Provider preferences and credential locations

Public Claude permissions use ordinary approval and no broad Bash allowlist. Optional model, plugin
and UI preferences are null (unmanaged) until added locally; the provider's type schema validates them.
Known objects merge recursively. Codex accepts `approval_policy` and `sandbox_mode` in the local
`codex` object, then uses its native versioned writer. Public defaults are `on-request`/`workspace-write`.

Pi starts unconfigured. Copy the `active` and `profiles` fields from
[the connection example](providers/pi/runtime/profiles.example.json) into local `pi`, then choose a
provider/model and supply the referenced key. `pi.secret_root` defaults to the AI checkout's ignored
`secrets/`; it can instead name an external directory. Relative locations resolve from the AI root. Windows drive and WSL drive-mount spellings map through the platform owner; Linux-only paths cannot silently become Windows paths.
A profile reference `secrets/provider.key` resolves beneath that directory. Traversal and escaping
symlinks refuse; validation checks file metadata without reading the key. The native auth command
reads the key only when Pi needs authentication. `pi.ownership_root` is a migration reference for an
existing native projection, not another source tree or credential store. Preserve its existing value
until a separately verified cutover transfers ownership. Neither check nor init moves secrets.

Use one private `config.local.jsonc` file; existing strict `config.local.json` files remain supported.
Both present, invalid comments, trailing commas and duplicate keys refuse. `make init` preserves existing
input byte for byte and seeds JSONC only when neither exists. The bundled, pinned comment parser needs
no package installation; native projections retain their native format. The commented example stays disabled; no
real connection or permissive operator preference belongs in tracked defaults. `make check` validates
configured profile structure; selected Pi install validates configured profiles against the installed
native catalog. Installation permits absent credentials; session startup requires a readable key.
Native profile scope, shared conversation discovery and reapplication/removal consequences belong
to [the Pi runtime owner](providers/pi/runtime/README.md).
