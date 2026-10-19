"""Transition property checks over a case rules.lean (task 1.3).

Appends #eval probes (test scaffolding, not reviewed rules) to a copy of the
case rules file and asserts: vote appends exactly one box entry, prepare makes
every ballot and delivers none, delivering to everyone reaches all-distributed,
double announce errors, out-of-window nominate rejects, and a vote refuses
with no ballot box.

QUORUM-FLAVOUR ONLY, and skipped with a printed reason rather than a bare Lean
failure for any case that does not define `applyDeliver`. A probe appended to
`rules.lean` cannot be written once for both mayor flavours: they disagree on the
arity of `Snapshot` (quorum carries the seeded paper supply, the instruments and
the mailboxes; `mayor-2027` carries none of them), so `Snapshot.mk` alone has
different arguments. Serving both needs either a probe per flavour or a self-test
hook each law defines for itself -- the hook is the better answer and is not
written. `requisitions` is a different law entirely (lodge/withdraw/settle) and
never had a probe.

Usage:
  uv run python tools/lawgen/check_apply_props.py cases/mayor-quorum
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# What the probe needs from the case. Each is a name the probe projects or calls,
# so a case missing one cannot compile the probe at all.
REQUIRES = ("applyDeliver", "applyPrepare", "deliverDue?", "freshCycle", "Owned")

PROBE = """
-- test scaffolding below (not part of the reviewed rules) --
def tAlice : Citizen := Citizen.mk "A" 71
def tBob : Citizen := Citizen.mk "B" 54
def tCara : Citizen := Citizen.mk "C" 43
def tCits : List Citizen := [tAlice, tBob, tCara]

-- A REAL cycle, so nothing below passes by having nothing to act on. The
-- Snapshot also carries the seeded paper supply, the instruments and the
-- mailboxes; a probe that left those empty would find no ballots to make and no
-- place to put them, and every distribution claim would be vacuously true.
--
-- Three citizens and two candidates is six ballots, so two sheets each is
-- exactly enough and the supply is not accidentally short.
def tCyc : Cycle := { (freshCycle 0) with
  candidates := ["B", "C"], registry := ["B", "C"], announced := true }
def tCycUnannounced : Cycle := { tCyc with announced := false }
def tSheets : List Owned :=
  [Owned.mk "sA1" "A", Owned.mk "sA2" "A", Owned.mk "sB1" "B",
   Owned.mk "sB2" "B", Owned.mk "sC1" "C", Owned.mk "sC2" "C"]
def tIns : List String := ["pen"]
def tMail : List Owned :=
  [Owned.mk "mA" "A", Owned.mk "mB" "B", Owned.mk "mC" "C"]
-- The one named thing `vote` acts on. Present, so the vote properties below are
-- about the vote and not about a missing box; the refusal when it is absent is
-- covered in test_oracle.py, which drives a client rather than a snapshot.
def tBoxes : List String := ["box"]

-- `none` for the office, so the authority falls back to the oldest citizen --
-- which is the law's own rule and keeps the probe independent of a seeded mayor.
def sAnn : Snapshot := Snapshot.mk 0 10 tCits [tCycUnannounced] none tSheets tIns tMail tBoxes
def sPrep : Snapshot := Snapshot.mk 9 10 tCits [tCyc] none tSheets tIns tMail tBoxes
def sOpen : Snapshot := Snapshot.mk 10 12 tCits [tCyc] none tSheets tIns tMail tBoxes

def isOk : Except String Snapshot → Bool
  | .ok _ => true
  | .error _ => false

-- 1. vote appends exactly one box entry
--    `box` lives on the Cycle, not the Snapshot: the box is the current
--    instance's, and a Snapshot holds the whole cycle history.
#eval match apply (Act.vote "A" "B") sOpen with
  | .ok s => (cur s).box.length == (cur sOpen).box.length + 1
             && (cur s).box.any (fun v => v.voter == "A")
  | .error _ => false

-- 2. prepare makes one ballot per citizen per candidate and delivers NONE of
--    them. The state between the two duties is what this law must be able to
--    hold, so it is asserted rather than assumed.
#eval match applyPrepare sPrep with
  | .ok s => (cur s).ballots.length == 6 && !(allDistributed? s)
            && (cur s).ballots.all (fun b => !b.delivered)
  | .error _ => false

-- 3. delivering to every recipient, and only then, reaches all-distributed
#eval match applyPrepare sPrep with
  | .error _ => false
  | .ok s1 => match applyDeliver s1 "A" with
    | .error _ => false
    | .ok s2 => match applyDeliver s2 "B" with
      | .error _ => false
      | .ok s3 => match applyDeliver s3 "C" with
        | .ok s4 => allDistributed? s4
        | .error _ => false

-- 4. double announce errors
#eval match apply .announce sAnn with
  | .ok s => !isOk (apply .announce s)
  | .error _ => false

-- 5. out-of-window nominate rejects
#eval match apply (Act.nominate "A") sOpen with
  | .ok _ => false
  | .error _ => true

-- 6. a vote refuses when the world has no ballot box to put it in
#eval match applyVote { sOpen with ballotBoxes := [] } "A" "B" with
  | .ok _ => false
  | .error _ => true
"""


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    case = (ROOT / argv[1]).resolve()
    src = (case / "rules.lean").read_text()
    missing = [name for name in REQUIRES if name not in src]
    if missing:
        # An explicit skip, not a pass and not a bare Lean failure: the case is a
        # different flavour and this probe was never written for it.
        print(f"skipped {case.name}: this probe is quorum-flavour, and the case "
              f"does not define {', '.join(missing)}. Nothing was checked.")
        return 0
    probe = Path(tempfile.mkdtemp(prefix="apply-props-")) / "Props.lean"
    probe.write_text(src + PROBE)
    proc = subprocess.run(["lake", "env", "lean", str(probe)],
                          capture_output=True, text=True,
                          cwd=ROOT / "lean", timeout=300)
    if proc.returncode != 0:
        print(f"probe failed:\n{proc.stderr.strip()}")
        return 1
    lines = [ln.strip() for ln in proc.stdout.strip().splitlines() if ln.strip()]
    ok = lines == ["true"] * 6
    for i, ln in enumerate(lines):
        print(f"prop{i + 1}: {ln}")
    if not ok:
        print(f"expected [true x6], got {lines}")
        return 1
    print("all transition properties hold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
