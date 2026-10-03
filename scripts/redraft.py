"""Step 1 draft-generation: law.txt in, draft ttl+lean+manifest out.

Report-only: renders the versioned prompt files with the case inputs so an
author (or LLM call) can produce drafts. No LLM API call here — the human
(or a later agentic loop) pastes the rendered prompt, saves stdout over the
draft files, and runs `scripts/check.py`.

Usage:
  uv run python scripts/redraft.py artefacts/mayor-2027 [--write-drafts]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = {
    # onto-v2 declares the framework invariants (ph:Citizen/Clock/CalendarPoint/
    # CalendarSpan) and the TBox-only rule; manifest-v2 adds holder_role,
    # params[] and readings. v1 files are kept for audit, not used.
    "ontology.ttl": ROOT / "prompts" / "onto-v2.md",
    "rules.lean": ROOT / "prompts" / "lean-v1.md",
    "manifest.yaml": ROOT / "prompts" / "manifest-v2.md",
}


def render(case: Path) -> dict[str, str]:
    law = (case / "law.txt").read_text()
    out: dict[str, str] = {}
    onto = PROMPTS["ontology.ttl"].read_text()
    out["ontology.ttl"] = onto + "\n---LAW---\n" + law
    lean = PROMPTS["rules.lean"].read_text()
    ontology = (case / "ontology.ttl").read_text() if (case / "ontology.ttl").exists() else ""
    out["rules.lean"] = lean + "\n---ONTOLOGY---\n" + ontology + "\n---LAW---\n" + law
    manifest = PROMPTS["manifest.yaml"].read_text()
    rules = (case / "rules.lean").read_text() if (case / "rules.lean").exists() else ""
    out["manifest.yaml"] = (
        manifest + "\n---ONTOLOGY---\n" + ontology + "\n---LEAN---\n" + rules
    )
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    case = (ROOT / argv[1]).resolve()
    if not (case / "law.txt").exists():
        print(f"error: no law.txt in {case}", file=sys.stderr)
        return 1
    rendered = render(case)
    if "--write-drafts" in argv:
        draft_dir = case / "drafts"
        draft_dir.mkdir(exist_ok=True)
        for name, text in rendered.items():
            (draft_dir / (name + ".prompt.md")).write_text(text)
            print(f"wrote {draft_dir / (name + '.prompt.md')}")
    else:
        for name, text in rendered.items():
            print(f"===== {name} prompt ({len(text)} bytes) =====")
            print(text[:400] + "\n... [truncated] ...\n")
    print("next: produce drafts, save as ontology.ttl/rules.lean/manifest.yaml, run scripts/check.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
