#!/usr/bin/env bash
# S5 — does a cold agent write each relationship and each contract exactly once?
# Criteria and receipt conventions: README.md beside this script.
#
#   s5-relationship-ownership.sh setup   <out>        explicit instruction arms: setup <out> <subject-agents> <control-agents>
#   s5-relationship-ownership.sh run     <out> <id>   one cold sample in a fresh mock; <id> is p<n> or r<n>
#   s5-relationship-ownership.sh signals <out>        grep hints per sample; the verdict is still read, not grepped
#
# <out> lies outside this repository and outside $HOME, and every sample is denied reads of both,
# so the only rules a sample can reach are the arm copy it is pointed at.
set -uo pipefail

# The caller supplies a control arm without the relationship-ownership rule.
CONTROL=${S5_CONTROL:-}
MODEL=${S5_MODEL:-}
HERE=$(cd "$(dirname "$0")" && pwd)
AGENTS=$(cd "$HERE/../.." && pwd -P)
REPO=$(cd "$AGENTS/.." && pwd -P)

# On WSL the Windows profile under /mnt also reaches the live skills, so it is denied as well.
WSL=0
case "$(uname -r)" in *[Mm]icrosoft*) WSL=1 ;; esac

die() { echo "s5: $*" >&2; exit 1; }

resolve_out() {
  [ -n "${1:-}" ] || die "missing <out>"
  local out
  out=$(realpath -m -- "$1")
  case "$out/" in
    "$REPO"/*|"$HOME"/*) die "<out> must lie outside the repository and \$HOME: $out" ;;
  esac
  if [ "$WSL" = 1 ]; then
    case "$out/" in /mnt/*) die "<out> must not lie under /mnt on WSL: $out" ;; esac
  fi
  printf '%s' "$out"
}

make_workspace() {
  local W=$1
  mkdir -p "$W/shop/services/checkout" "$W/shop/services/payments/api" "$W/ledger/api" "$W/ledger/src"

  cat > "$W/shop/README.md" <<'EOF'
# shop

Online shop backend.

| path | owns |
|---|---|
| [services/](services/README.md) | the runtime services |
EOF

  cat > "$W/shop/services/README.md" <<'EOF'
# services

The shop's runtime services.

| path | owns |
|---|---|
| [checkout/](checkout/README.md) | turning a cart into a paid order |
| [payments/](payments/README.md) | charging customers through the card processor |
EOF

  cat > "$W/shop/services/checkout/README.md" <<'EOF'
# checkout

Turns a cart into a paid order. Entry point: `service.py`.
EOF

  cat > "$W/shop/services/checkout/service.py" <<'EOF'
import psycopg

from ledger_client import LedgerStub  # generated from the ledger repository's api/ledger.proto
from services.payments.api.payments_api import CaptureFailed, PaymentsApi


class Checkout:
    def __init__(self, payments: PaymentsApi, ledger: LedgerStub, db: psycopg.Connection):
        self.payments, self.ledger, self.db = payments, ledger, db

    def complete(self, order_id: str, amount_cents: int) -> None:
        key = f"order-{order_id}"
        try:
            charge = self.payments.capture(order_id, amount_cents, idempotency_key=key)
        except CaptureFailed:
            # One retry: a capture failure is usually a transient processor timeout.
            charge = self.payments.capture(order_id, amount_cents, idempotency_key=key)
        self.ledger.RecordEntry(order_id=order_id, amount_cents=amount_cents, charge_id=charge.id)
        with self.db.transaction():
            self.db.execute("UPDATE orders SET state = 'paid' WHERE id = %s", (order_id,))
EOF

  cat > "$W/shop/services/payments/README.md" <<'EOF'
# payments

Charges customers through the card processor. Public interface: `api/payments_api.py`.
EOF

  cat > "$W/shop/services/payments/api/payments_api.py" <<'EOF'
from dataclasses import dataclass
from typing import Protocol


class CaptureFailed(Exception):
    pass


@dataclass
class Charge:
    id: str
    amount_cents: int


class PaymentsApi(Protocol):
    def capture(self, order_id: str, amount_cents: int, idempotency_key: str) -> Charge:
        """Capture a charge. Repeating a call with the same idempotency_key returns the original Charge."""
EOF

  cat > "$W/shop/services/payments/processor.py" <<'EOF'
import httpx

from .api.payments_api import CaptureFailed, Charge

PROCESSOR_URL = "https://api.card-processor.example/v2/captures"


class Payments:
    def __init__(self, http: httpx.Client, seen: dict[str, Charge]):
        self.http, self.seen = http, seen

    def capture(self, order_id: str, amount_cents: int, idempotency_key: str) -> Charge:
        if idempotency_key in self.seen:
            return self.seen[idempotency_key]
        r = self.http.post(PROCESSOR_URL, json={"reference": order_id, "amount": amount_cents},
                           headers={"Idempotency-Key": idempotency_key}, timeout=5)
        if r.status_code >= 500:
            raise CaptureFailed(r.text)
        charge = Charge(id=r.json()["id"], amount_cents=amount_cents)
        self.seen[idempotency_key] = charge
        return charge
EOF

  cat > "$W/ledger/README.md" <<'EOF'
# ledger

Double-entry accounting ledger shared by several products. Public interface: `api/ledger.proto`.
EOF

  cat > "$W/ledger/api/ledger.proto" <<'EOF'
syntax = "proto3";
package ledger.v1;

service Ledger {
  // Idempotent per charge_id.
  rpc RecordEntry(RecordEntryRequest) returns (RecordEntryReply);
}

message RecordEntryRequest {
  string order_id = 1;
  int64 amount_cents = 2;
  string charge_id = 3;
}

message RecordEntryReply {
  string entry_id = 1;
}
EOF

  cat > "$W/ledger/src/server.py" <<'EOF'
class LedgerServicer:
    def __init__(self, entries: dict[str, str]):
        self.entries = entries

    def RecordEntry(self, request, context):
        if request.charge_id not in self.entries:
            self.entries[request.charge_id] = f"entry-{len(self.entries) + 1}"
        return {"entry_id": self.entries[request.charge_id]}
EOF
}

# The prompt names neither the rule nor the arm; the placeholders are the only per-sample text.
prompt_for() {
  local p
  p=$(cat <<'EOF'
You are working in two separate repositories, each with its own documentation tree:
- __W__/shop
- __W__/ledger
Neither has architecture documentation yet.

Standing instructions: before anything else, read __INSTR__/AGENTS.md and follow it. Where it refers to paths relative to its own SOT directory, that directory is __INSTR__.

Task: write the architecture documentation for shop's services — the services scope, checkout, and payments — and for ledger, so that a new engineer can understand how each part fits in. Base it on the code. Create the files.

Constraints: write only under __W__. Do not modify the existing code.

When done, reply with exactly these lines and nothing else:
FILES_WRITTEN: <comma-separated paths relative to __W__>
INSTRUCTION_FILES_READ: <paths relative to __INSTR__, in order>
PLACEMENT_NOTE: <one sentence on the hardest placement decision you made>
EOF
)
  p=${p//__W__/$1}
  printf '%s\n' "${p//__INSTR__/$2}"
}

cmd_setup() {
  local out
  out=$(resolve_out "${1:-}") || exit 1
  [ ! -e "$out" ] && [ ! -L "$out" ] || die "choose a fresh <out>; existing evidence is preserved"
  local subject=${2:-${S5_SUBJECT:-$AGENTS}} control=${3:-$CONTROL}
  [ -n "$control" ] || die "setup requires an explicit control agents directory"
  python3 - "$subject" "$control" "$out" <<'PYSETUP'
import hashlib,json,shutil,sys
from pathlib import Path
subject,control,out=map(Path,sys.argv[1:])
identities={}
for label,source in [('p',subject),('r',control)]:
    assert (source/'AGENTS.md').is_file() and (source/'skills').is_dir(), 'instruction arm needs AGENTS.md and skills/'
    entries=[source/'AGENTS.md']+[p for p in (source/'skills').rglob('*') if not {'synced','.trash','__pycache__'}.intersection(p.relative_to(source).parts)]
    assert not any(p.is_symlink() for p in entries), 'instruction arms must not contain links'
    digest=hashlib.sha256()
    for p in sorted(p for p in entries if p.is_file()):
        digest.update(str(p.relative_to(source)).encode());digest.update(p.read_bytes())
    identities[label]=digest.hexdigest()
out.mkdir(parents=True)
for label,source in [('p',subject),('r',control)]:
    destination=out/('instr-'+label);destination.mkdir()
    shutil.copyfile(source/'AGENTS.md',destination/'AGENTS.md')
    shutil.copytree(source/'skills',destination/'skills',ignore=shutil.ignore_patterns('synced','.trash','__pycache__'))
(out/'inputs.json').write_text(json.dumps(identities,indent=2)+'\n')
(out/'.s5').touch()
PYSETUP
  [ $? == 0 ] || die "instruction arm setup failed"
  echo "s5: explicit instruction arms and content identities prepared"

}

cmd_run() {
  local out id W INSTR deny start rc
  out=$(resolve_out "${1:-}") || exit 1
  [ -n "$MODEL" ] || die "a paid evaluation requires explicit S5_MODEL and separate operator authorization"
  id=${2:-}
  [[ $id =~ ^[pr][0-9]+$ ]] || die "<id> must be p<n> or r<n>"
  [ -e "$out/.s5" ] || die "run setup first"
  W=$out/ws-$id
  INSTR=$out/instr-${id:0:1}
  [ -e "$W" ] && die "$W exists; a sample starts from an untouched workspace"
  make_workspace "$W"
  deny="Bash,WebFetch,WebSearch,Agent,Read(/$REPO/**),Read(/$HOME/**)"
  [ "$WSL" = 1 ] && deny="$deny,Read(//mnt/**)"
  cd "$W" || die "cannot enter $W"
  start=$(date +%s)
  prompt_for "$W" "$INSTR" | claude -p --safe-mode --model "$MODEL" --permission-mode acceptEdits \
    --add-dir "$INSTR" \
    --allowedTools "Read,Write,Edit,Glob,Grep" \
    --disallowedTools "$deny" \
    --no-session-persistence --output-format json >"$out/$id.json" 2>"$out/$id.err"
  rc=${PIPESTATUS[1]}
  echo "s5: $id exit=$rc wall=$(( $(date +%s) - start ))s"
  return "$rc"
}

# Each hint prints its count and the matching lines; W is the sample being read.
hits() {
  local label=$1 lines
  shift
  lines=$("$@" 2>/dev/null)
  echo "  $label: $(printf '%s' "$lines" | grep -c .)"
  [ -n "$lines" ] && printf '%s\n' "$lines" | sed "s#^$W/##; s/^/      /" | cut -c1-140
  return 0
}
direction_in_structure() { grep -rniE --include=structure.md -e "→|-->|depends on|dependency on" "$W"; }
payments_names_checkout() { grep -rni checkout "$W/shop/services/payments" --include='*.md' | grep -v ']('; }
ledger_names_consumer() { grep -rniE "shop|checkout" "$W/ledger" --include='*.md'; }
services_names_child_externals() { grep -rniE "ledger|postgres|card processor" "$W/shop/services/docs"; }
contract_shape_copied() { grep -rnE "capture\(|RecordEntry\(|Charge\(id|order id, the amount|\"reference\"" "$W" --include='*.md'; }
parent_view_draws_child_edges() { grep -rniE "ledger|postgres|processor" "$W/shop/services/docs/architecture/diagrams"; }

cmd_signals() {
  local out W id
  out=$(resolve_out "${1:-}") || exit 1
  for W in "$out"/ws-*; do
    [ -d "$W" ] || continue
    id=${W##*/ws-}
    echo "==== $id"
    python3 - "$out/$id.json" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except (OSError, ValueError) as e:
    print(f"  no result: {e}")
    sys.exit()
print(f"  turns={d.get('num_turns')} cost_usd={d.get('total_cost_usd')} "
      f"duration_ms={d.get('duration_ms')} is_error={d.get('is_error')}")
PY
    hits "C1-C3 direction restated in structure.md prose" direction_in_structure
    hits "C1 payments names checkout outside a link" payments_names_checkout
    hits "C2 ledger names a consumer" ledger_names_consumer
    hits "C3 services docs name a child's external" services_names_child_externals
    hits "C4 contract shape copied into docs" contract_shape_copied
    hits "C5 services view draws a child's edges" parent_view_draws_child_edges
  done
}

case "${1:-}" in
  setup) cmd_setup "${2:-}" "${3:-}" "${4:-}" ;;
  run) cmd_run "${2:-}" "${3:-}" ;;
  signals) cmd_signals "${2:-}" ;;
  *) sed -n '2,10p' "$0"; exit 2 ;;
esac
