#!/usr/bin/env bash
# Invoke through `bash` - the Windows drive mounts with fmask=0133, so this file can
# never carry an execute bit from WSL.
# No venv: the suite reads markdown with the standard library only, so it runs anywhere
# the repository is checked out.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
python3 -m unittest discover -s . -p "test_*.py" -t . "$@"
echo
python3 report_cost.py
