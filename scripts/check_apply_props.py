"""Transition property checks over a case rules.lean (task 1.3).

Appends #eval probes (test scaffolding, not reviewed rules) to a copy of the
case rules file and asserts: vote appends exactly one box entry, prepare
yields all-distributed, double announce errors.

Usage:
  uv run python scripts/check_apply_props.py artefacts/mayor-2027
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROBE = """
-- test scaffolding below (not part of the reviewed rules) --
def tAlice : Citizen := Citizen.mk "A" 71
def tBob : Citizen := Citizen.mk "B" 54
def tCara : Citizen := Citizen.mk "C" 43
def tCits : List Citizen := [tAlice, tBob, tCara]

def sAnn : Snapshot := Snapshot.mk 0 10 tCits [] [] [] [] false false false false none
def sPrep : Snapshot := Snapshot.mk 9 10 tCits ["B", "C"] [] ["B", "C"] [] true false false false none
def sOpen : Snapshot := Snapshot.mk 10 12 tCits ["B", "C"] [] ["B", "C"] [] true true false false none

def isOk : Except String Snapshot → Bool
  | .ok _ => true
  | .error _ => false

-- vote appends exactly one box entry
#eval match apply (Act.vote "A" "B") sOpen with
  | .ok s => s.box.length == sOpen.box.length + 1 && s.box.any (fun v => v.voter == "A")
  | .error _ => false
-- prepare yields all-distributed
#eval match applyPrepare sPrep with
  | .ok s => allDistributed? s
  | .error _ => false
-- double announce errors
#eval match apply .announce sAnn with
  | .ok s => !isOk (apply .announce s)
  | .error _ => false
-- out-of-window nominate rejects
#eval match apply (Act.nominate "A") sOpen with
  | .ok _ => false
  | .error _ => true
"""


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    case = (ROOT / argv[1]).resolve()
    src = (case / "rules.lean").read_text()
    probe = Path(tempfile.mkdtemp(prefix="apply-props-")) / "Props.lean"
    probe.write_text(src + PROBE)
    proc = subprocess.run(["lake", "env", "lean", str(probe)],
                          capture_output=True, text=True,
                          cwd=ROOT / "potato-hamlet-lean", timeout=300)
    if proc.returncode != 0:
        print(f"probe failed:\n{proc.stderr.strip()}")
        return 1
    lines = [ln.strip() for ln in proc.stdout.strip().splitlines() if ln.strip()]
    ok = lines == ["true"] * 4
    for i, ln in enumerate(lines):
        print(f"prop{i + 1}: {ln}")
    if not ok:
        print(f"expected [true x4], got {lines}")
        return 1
    print("all transition properties hold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
