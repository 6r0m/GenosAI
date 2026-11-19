# Private AI credentials

This directory holds user-supplied AI credential files and is ignored except for this README.
Agent providers own credential references and validation; actual values never belong in profiles,
examples, logs, source archives, or native configuration projections.

Pi defaults to this directory. An ignored local `pi.secret_root` can select an existing external
store instead; relative locations resolve from the AI checkout root. Keep Git-helper, console,
worker, and native Claude/Codex sign-in credentials with their existing owners.
