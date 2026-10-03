"""Review gate: freeze a reviewed artefact set, verify frozen sets.

Freeze (human act after reviewing drafts + green checks):
  uv run python scripts/freeze.py artefacts/mayor-2027
  -> runs scripts/check.py first; on pass writes manifest freeze hash
     (sha256 over law.txt + ontology.ttl + rules.lean + manifest body).

Verify (consumer/TUI entry point, Phase 2 calls this before loading):
  uv run python scripts/freeze.py --verify artefacts/mayor-2027
  -> exit 0 iff frozen and no file changed; names changed files otherwise.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
# population.ttl is tracked: the spec puts the seeded individuals in the
# variant layout, and a freeze that ignores the seed is not a freeze of the
# set. It was omitted while the seed still lived inside ontology.ttl, which
# WAS tracked -- moving the individuals out silently dropped them from the
# hash.
TRACKED = ["law.txt", "ontology.ttl", "population.ttl", "rules.lean"]


def digest(case: Path, manifest_body: dict) -> str:
    h = hashlib.sha256()
    for name in TRACKED:
        h.update((case / name).read_bytes())
        h.update(b"\0")
    h.update(yaml.safe_dump(manifest_body, sort_keys=True).encode())
    h.update(b"\0")
    return "sha256:" + h.hexdigest()


def manifest_body(case: Path) -> dict:
    data = yaml.safe_load((case / "manifest.yaml").read_text())
    return {k: v for k, v in data.items() if k != "freeze"}


def freeze(case: Path) -> int:
    proc = subprocess.run(
        ["uv", "run", "python", "scripts/check.py", str(case.relative_to(ROOT))],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    print(proc.stdout, end="")
    if proc.returncode != 0:
        print("freeze refused: machine checks fail.", file=sys.stderr)
        return 1
    body = manifest_body(case)
    data = yaml.safe_load((case / "manifest.yaml").read_text())
    data["freeze"] = digest(case, body)
    (case / "manifest.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    print(f"frozen {case.relative_to(ROOT)}: {data['freeze']}")
    return 0


def verify(case: Path) -> int:
    data = yaml.safe_load((case / "manifest.yaml").read_text())
    frozen = data.get("freeze")
    if not frozen:
        print(f"unfrozen: {case.relative_to(ROOT)} has no freeze mark (run scripts/freeze.py).")
        return 1
    changed = []
    for name in TRACKED:
        if not (case / name).exists():
            changed.append(f"{name} (missing)")
    body = {k: v for k, v in data.items() if k != "freeze"}
    if digest(case, body) != frozen:
        # Which file changed cannot be recovered from a single combined hash,
        # so the whole set is reported. Built from TRACKED rather than written
        # out: a hardcoded list goes stale the moment a file is added, and then
        # it names files that did not change while omitting the one that did.
        # Per-file mtimes guide the author to the culprit.
        changed.append(
            "one or more of " + " / ".join(TRACKED) + " / manifest body "
            "(hash mismatch; the combined hash cannot say which)"
        )
    if changed:
        print(f"refused: {case.relative_to(ROOT)} changed after freeze:")
        for c in changed:
            print(f"  {c}")
        return 1
    print(f"verified frozen: {case.relative_to(ROOT)}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    if argv[1] == "--verify":
        return verify((ROOT / argv[2]).resolve())
    return freeze((ROOT / argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
