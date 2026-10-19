"""Step 1 draft-generation: law.txt in, draft ttl+lean+manifest out.

Report-only: renders the versioned prompt files with the case inputs so an
author (or LLM call) can produce drafts. No LLM API call here — the human
(or a later agentic loop) pastes the rendered prompt, saves stdout over the
draft files, and runs `tools/lawgen/check.py`.

Usage:
  uv run python tools/lawgen/redraft.py cases/mayor-2027 [--write-drafts]
  uv run python tools/lawgen/redraft.py cases/mayor-2027 --json /tmp/rendered
      (machine-readable render output pi can call: writes
      ontology.ttl.prompt.md, rules.lean.prompt.md, manifest.yaml.prompt.md
      plus render.json; the default paths above are byte-identical)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PROMPTS = {
    # onto-v2 declares the framework invariants (ph:Citizen/Clock/CalendarPoint/
    # CalendarSpan) and the TBox-only rule; manifest-v2 adds holder_role,
    # params[] and readings. v1 files are kept for audit, not used.
    "ontology.ttl": ROOT / "tools" / "lawgen" / "prompts" / "onto-v2.md",
    "rules.lean": ROOT / "tools" / "lawgen" / "prompts" / "lean-v1.md",
    "manifest.yaml": ROOT / "tools" / "lawgen" / "prompts" / "manifest-v2.md",
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
    # Machine-readable render output pi can call. Separate flag, separate
    # path: the default preview and --write-drafts branches below are
    # untouched, so current render behaviour is byte-identical for existing
    # users. redraft.py stays render-and-stop unconditionally -- it never
    # grows a loop driver.
    if "--json" in argv:
        dest = Path(argv[argv.index("--json") + 1])
        dest.mkdir(parents=True, exist_ok=True)
        for name, text in rendered.items():
            (dest / (name + ".prompt.md")).write_text(text)
        (dest / "render.json").write_text(json.dumps(
            {name: len(text) for name, text in rendered.items()}, indent=2) + "\n")
        print(f"wrote {len(rendered)} rendered prompts to {dest}")
        return 0
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
    print("next: produce drafts, save as ontology.ttl/rules.lean/manifest.yaml, run tools/lawgen/check.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
