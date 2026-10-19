"""Deterministic fake extractor for the clarification loop (CI-only, never user-facing).

No LLM credential exists in this environment, so the loop's convergence, the
question round, and the prompt contract stay testable through this fake plus
the minimal headless driver (`tools/lawgen/clarification_driver.py`). The fake
reads a SCRIPTED sequence of reports -- a JSON file naming, per pass, which
{step, why-ungroundable} entries the "extractor" returns and which draft files
it produces -- so every run is byte-deterministic without a model.

Crucially, the fake can REPORT QUESTIONS: a fake that never asks would make
the loop look converged forever, which is the one behaviour most worth
testing. Pass 0 of a script normally carries a non-empty report; the driver
must then stop with questions outstanding (non-zero exit) when no answers are
given, and converge only when the script's later passes answer them.

Answers change the draft rather than being logged: the fake splices each
pass's given answers into the next pass's draft (as a grounded declaration
comment naming the answered step), so a test can assert the draft moved
because of the answer. The script's per-pass `draft_overlay` supplies the
rest of the draft content; the converged pass normally overlays the real
shipped artefact files.

Script shape:
  {"passes": [{"report": [{"step": ..., "why-ungroundable": ...}, ...],
               "draft_overlay": {"ontology.ttl": ..., "population.ttl": ...,
                                 "rules.lean": ..., "manifest.yaml": ...}},
              ...]}

Usage as a module:
  from fake_extractor import FakeExtractor
  fake = FakeExtractor(script_path)
  drafts, report = fake.extract(pass_index=0, answers={})

Usage as a CLI (one pass, for debugging):
  uv run python tools/lawgen/fake_extractor.py script.json --pass 0 [--answers answers.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DRAFT_FILES = ("ontology.ttl", "population.ttl", "rules.lean", "manifest.yaml")


class FakeExtractor:
    """A scripted extractor: deterministic drafts plus reports, no credential."""

    def __init__(self, script_path: Path):
        self.script_path = Path(script_path)
        try:
            self.script = json.loads(self.script_path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"fake script {script_path} is unreadable: {e}") from e
        if not isinstance(self.script.get("passes"), list) or not self.script["passes"]:
            raise ValueError(f"fake script {script_path} must hold a non-empty 'passes' list")

    def extract(self, pass_index: int, answers: dict[str, str]) -> tuple[dict[str, str], dict]:
        """Return (drafts, report) for one pass.

        `answers` maps step text -> answer text given so far. Every answered
        step is spliced into the draft as a grounded declaration, so the next
        pass's draft visibly carries the answer rather than merely logging it.
        A pass beyond the script's end repeats the last pass (converged stays
        converged; unconverged stays unconverged).
        """
        passes = self.script["passes"]
        spec = passes[min(pass_index, len(passes) - 1)]
        overlay = spec.get("draft_overlay") or {}
        # Answers land IN the declarations' files as comments naming the
        # answered step, so the next pass's draft visibly carries the answer
        # rather than merely logging it. Comment syntax is per file: `#` is
        # Turtle's comment but not Lean's, so rules.lean gets `--`.
        answer_lines = sorted(answers.items())
        ttl_block = "".join(f"\n# Grounded per author answer to {s!r}: {a}" for s, a in answer_lines)
        lean_block = "".join(f"\n-- Grounded per author answer to {s!r}: {a}" for s, a in answer_lines)
        drafts = {
            "ontology.ttl": overlay.get("ontology.ttl", "") + ttl_block,
            "population.ttl": overlay.get("population.ttl", ""),
            "rules.lean": overlay.get("rules.lean", "") + lean_block,
            "manifest.yaml": overlay.get("manifest.yaml", ""),
        }
        report = {"report": [dict(e) for e in spec.get("report", [])]}
        return drafts, report


def main(argv: list[str]) -> int:
    if len(argv) < 2 or "--pass" not in argv:
        print(__doc__)
        return 2
    script = Path(argv[1])
    pass_index = int(argv[argv.index("--pass") + 1])
    answers: dict[str, str] = {}
    if "--answers" in argv:
        answers = json.loads(Path(argv[argv.index("--answers") + 1]).read_text())
    try:
        fake = FakeExtractor(script)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    drafts, report = fake.extract(pass_index, answers)
    out = {"drafts": {k: v[:200] for k, v in drafts.items()}, "report": report}
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
