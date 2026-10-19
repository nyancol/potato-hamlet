"""The clarification loop's convergence claim, proved without a credential.

The product loop runs in pi; this suite pins what the headless test double
proves in its place: the fake asks (2.4), the driver runs with no credential
(3.1), stops non-zero with drafts plus report when questions remain (3.2),
feeds answers back so they change the draft (3.3), never re-asks a stalled
step (3.4), converges on mayor-2027 to a draft the gate passes over the world
fixture (4.1), is refused when stopped early with an undeclared class (4.2),
asks nothing of a fully-covered law (4.3), and never asks the same question
twice (4.4).

Usage:
  uv run python tests/test_clarification_loop.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "lawgen"))

import check  # noqa: E402
from fake_extractor import FakeExtractor  # noqa: E402

fails: list[str] = []


def expect(name: str, cond: bool, detail: str = "") -> None:
    print(("PASS " if cond else "FAIL ") + name + (f" ({detail})" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def run_driver(case: str, script: dict, out: Path, answers: dict | None = None,
               gate_mode: str = "schema") -> tuple[int, str]:
    sp = out.parent / (out.name + ".script.json")
    sp.write_text(json.dumps(script))
    cmd = [sys.executable, str(ROOT / "tools" / "lawgen" / "clarification_driver.py"),
           "--case", case, "--script", str(sp), "--out", str(out),
           "--gate-mode", gate_mode]
    if answers is not None:
        ap = out.parent / (out.name + ".answers.json")
        ap.write_text(json.dumps(answers))
        cmd += ["--answers", str(ap)]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return proc.returncode, proc.stdout + proc.stderr


def shipped(case: str) -> dict[str, str]:
    d = ROOT / "cases" / case
    return {n: (d / n).read_text() for n in ("ontology.ttl", "population.ttl", "rules.lean", "manifest.yaml")}


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="clarif-test-"))

    # --- 2.4: the fake reports questions; the driver stops outstanding ----
    code, log = run_driver("cases/mayor-2027",
                           {"passes": [{"report": [{"step": "Who delivers the papers, and by when?",
                                                    "why-ungroundable": "No declared capability accounts for delivery"}],
                                        "draft_overlay": {}}]},
                           tmp / "q-out")
    expect("2.4 driver stops non-zero with questions outstanding", code != 0, log[-500:])
    expect("2.4 drafts plus report are written",
           (tmp / "q-out" / "ontology.ttl").exists() and (tmp / "q-out" / "report.json").exists())
    expect("2.4 questions are presented as questions",
           (tmp / "q-out" / "questions.json").exists()
           and "delivers the papers" in (tmp / "q-out" / "questions.json").read_text())

    # --- 3.3: an answer changes the draft, not just the log ---------------
    fake = FakeExtractor(_write(tmp / "s33.json", {"passes": [{"report": [], "draft_overlay": {}}]}))
    before, _ = fake.extract(0, {})
    after, _ = fake.extract(1, {"Who delivers?": "The mayor, within a day"})
    expect("3.3 an answer lands in the next draft",
           "The mayor, within a day" in after["ontology.ttl"]
           and "The mayor, within a day" not in before["ontology.ttl"])

    # --- 3.4 + 4.4: a stalled step is never asked twice --------------------
    stall = {"passes": [
        {"report": [{"step": "What is a quorum here?", "why-ungroundable": "No declared capability accounts for it"}],
         "draft_overlay": {}},
        {"report": [{"step": "What is a quorum here?", "why-ungroundable": "No declared capability accounts for it"}],
         "draft_overlay": {}}]}
    code, log = run_driver("cases/mayor-2027", stall, tmp / "stall-out",
                           answers={"What is a quorum here?": "Half the hamlet"})
    expect("3.4 a step asked and still ungrounded stops the driver, not a loop", code != 0, log[-500:])
    expect("3.4 the stall is recorded as no-progress", "no progress" in log)
    asked = [q["step"] for q in json.loads((tmp / "stall-out" / "questions.json").read_text())]
    expect("4.4 the same question is never asked twice", asked == ["What is a quorum here?"], str(asked))

    # --- 4.3: a fully-covered law asks nothing ------------------------------
    code, log = run_driver("cases/mayor-2027",
                           {"passes": [{"report": [], "draft_overlay": shipped("mayor-2027")}]},
                           tmp / "covered-out")
    expect("4.3 a fully-covered law converges asking nothing", code == 0, log[-500:])
    expect("4.3 no questions file when nothing was asked",
           not (tmp / "covered-out" / "questions.json").exists())

    # --- 4.1: mayor-2027 converges to a draft the gate passes ---------------
    step = "Who delivers the papers, and by when?"
    conv = {"passes": [
        {"report": [{"step": step, "why-ungroundable": "No declared capability accounts for delivery"}],
         "draft_overlay": {}},
        {"report": [], "draft_overlay": shipped("mayor-2027")}]}
    code, log = run_driver("cases/mayor-2027", conv, tmp / "conv-out",
                           answers={step: "The mayor, into each mailbox"})
    expect("4.1 the headless driver converges on mayor-2027", code == 0, log[-800:])
    _, errors, _ = check.run(tmp / "conv-out", schema_only=True)
    expect("4.1 the converged draft passes the gate over the world merge", errors == [], str(errors[:3]))

    # --- 4.2: stopping early with an undeclared class is refused ------------
    early = dict(shipped("mayor-2027"))
    early["ontology.ttl"] += "\nph:BallotVote rdfs:subClassOf ph:SomethingNobodyDeclared .\n"
    for name, text in early.items():
        (tmp / "conv-out" / name).write_text(text)
    _, errors, _ = check.run(tmp / "conv-out", schema_only=True)
    expect("4.2 a draft stopped early on an undeclared class is refused",
           any("SomethingNobodyDeclared" in e for e in errors), str(errors[:2]))

    print(f"\n{'all pass' if not fails else f'{len(fails)} FAILURES: {fails}'}")
    return 1 if fails else 0


def _write(path: Path, obj: dict) -> Path:
    path.write_text(json.dumps(obj))
    return path


if __name__ == "__main__":
    raise SystemExit(main())
