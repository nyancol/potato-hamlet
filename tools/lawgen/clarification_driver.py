"""Minimal headless clarification-loop driver (CI-only, never user-facing).

The product loop runs in a pi session, which needs a credential this
environment does not have. This driver mirrors its rules headlessly so the
loop's convergence, the question round, and the prompt contract stay provable
without a key: render, validate the report, run the gate over the world
fixture -- extract, collect the report, and while it is non-empty present the
steps as questions and re-extract with the answers.

Loop rules (mirroring the pi-side contract in
`tools/lawgen/clarification-loop-pi-contract.md`):
  - Terminate only on an empty report. A run ending non-empty writes its
    drafts plus the report and exits non-zero, so nothing downstream mistakes
    an unconverged draft for a finished one.
  - Never ask the same step twice. A step that was asked about and comes back
    ungrounded is NOT asked again: the driver records the stall ("no
    progress") and exits non-zero rather than spinning forever.
  - Answers come from an answers file (the headless stand-in for the author).
    A question with no answer stops the run with questions outstanding.

Usage:
  uv run python tools/lawgen/clarification_driver.py --case cases/mayor-2027 \\
      --script /tmp/script.json --out /tmp/loop-out [--answers /tmp/answers.json] \\
      [--max-passes 5] [--gate-mode schema|full]

Exit 0 only when the report is empty AND the gate passes over the world merge.
Exit 1 with drafts plus report.json (and questions.json when questions were
asked) written to --out otherwise. No credential is used at any point: the
extractor is the deterministic fake, the renderer is stateless `redraft.py`,
and the gate is the repo's own `check.py`.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools" / "lawgen"))

import check  # noqa: E402
import redraft  # noqa: E402
from fake_extractor import FakeExtractor  # noqa: E402
from validate_report import validate  # noqa: E402

DRAFT_FILES = ("ontology.ttl", "population.ttl", "rules.lean", "manifest.yaml")


def write_outputs(out: Path, drafts: dict[str, str], report: dict, questions: list[dict]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name in DRAFT_FILES:
        (out / name).write_text(drafts.get(name, ""))
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    if questions:
        (out / "questions.json").write_text(json.dumps(questions, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--case", required=True, help="Input case dir (law.txt source; copied so the gate sees a full set)")
    ap.add_argument("--script", required=True, help="Fake extractor script JSON")
    ap.add_argument("--out", required=True, help="Output dir for drafts + report.json (+ questions.json)")
    ap.add_argument("--answers", default=None, help="Answers JSON mapping step text -> answer text")
    ap.add_argument("--max-passes", type=int, default=5)
    ap.add_argument("--gate-mode", choices=("schema", "full"), default="schema")
    args = ap.parse_args(argv)

    case = (ROOT / args.case).resolve() if not Path(args.case).is_absolute() else Path(args.case)
    out = Path(args.out)
    if not (case / "law.txt").exists():
        print(f"error: no law.txt in {case}", file=sys.stderr)
        return 1

    # Render first: the stateless prompt render is what the product loop calls,
    # so the headless run proves the prompt contract it would feed a model.
    rendered = redraft.render(case)
    assert set(rendered) == {"ontology.ttl", "rules.lean", "manifest.yaml"}, set(rendered)

    try:
        fake = FakeExtractor(Path(args.script))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    answer_bank: dict[str, str] = {}
    if args.answers:
        answer_bank = json.loads(Path(args.answers).read_text())
        if not isinstance(answer_bank, dict):
            print("error: answers file must be a JSON object", file=sys.stderr)
            return 1

    # Seed the output with the input case so the gate sees a full artefact set
    # (law.txt, oracle binary); each pass overwrites only the four drafts.
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(case, out, ignore=shutil.ignore_patterns("drafts"))

    answers_given: dict[str, str] = {}
    asked: set[str] = set()
    questions: list[dict] = []
    pass_index = 0
    while True:
        drafts, report = fake.extract(pass_index, answers_given)
        violations = validate(report)
        if violations:
            write_outputs(out, drafts, report, questions)
            for v in violations:
                print(f"invalid report on pass {pass_index}: {v}", file=sys.stderr)
            return 1
        entries = report["report"]
        if not entries:
            write_outputs(out, drafts, report, questions)
            _, errors, _ = check.run(out, schema_only=(args.gate_mode == "schema"))
            if errors:
                print(f"converged but the gate refuses the draft ({len(errors)} problem(s)):", file=sys.stderr)
                for e in errors[:10]:
                    print(f"  {e}", file=sys.stderr)
                return 1
            print(f"converged after {pass_index} re-extraction(s): gate passes over the world merge")
            return 0
        fresh = [e for e in entries if e["step"] not in asked]
        if not fresh:
            # No-progress guard: every outstanding step was already asked and
            # answered, yet the extractor still cannot ground it. Asking again
            # would spin forever, so record the stall and stop.
            write_outputs(out, drafts, report, questions)
            print(f"no progress on pass {pass_index}: every outstanding step was already "
                  f"asked ({len(entries)} still ungrounded) -- stopping rather than re-asking",
                  file=sys.stderr)
            return 1
        for e in fresh:
            questions.append({"step": e["step"], "why": e["why-ungroundable"], "pass": pass_index})
            print(f"Q (pass {pass_index}): {e['step']} -- {e['why-ungroundable']}")
        missing = [e["step"] for e in fresh if e["step"] not in answer_bank]
        if missing:
            write_outputs(out, drafts, report, questions)
            print(f"questions outstanding ({len(missing)} unanswered): draft is not complete",
                  file=sys.stderr)
            return 1
        for e in fresh:
            answers_given[e["step"]] = answer_bank[e["step"]]
            asked.add(e["step"])
        pass_index += 1
        if pass_index >= args.max_passes:
            drafts, report = fake.extract(pass_index, answers_given)
            write_outputs(out, drafts, report, questions)
            print(f"pass budget exhausted ({args.max_passes}): draft is not complete", file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
