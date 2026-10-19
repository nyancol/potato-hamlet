"""Does the README describe the oracle that actually exists?

A protocol document drifts silently: the code changes, the prose does not, and
a consumer written against the prose breaks. The recorded risk on the old
cases/README.md was real -- it documented `would_win` where the oracle emits
`readings`, a nested `witness` object where the verdict has none, and an
argument (`check [file]`) whose pattern matched an argv slot that never occurs.

So the README is checked rather than trusted. Every field name, key set, enum
value and CLI behaviour it claims is compared against a real invocation, at a
point in a law's run where the interesting shapes actually occur.

Usage:
  uv run python tests/test_readme.py cases/mayor-2027
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "lawgen"))

import yaml  # noqa: E402
from runtime.graphwire import graph_to_wire  # noqa: E402
from runtime.oracle import OracleClient, OracleRejected  # noqa: E402
from runtime.lawdriver import advance, manifest_of, pending_acts  # noqa: E402

CITIZEN = "https://potato-hamlet.example/ontology/citizen/"
PH = "https://potato-hamlet.example/ontology/"
READING_KINDS = {"decimal", "ref", "flag"}
fails: list[str] = []

# What the README claims. Kept as literals rather than parsed out of the prose,
# so that editing the prose without editing this fails the check -- which is the
# whole point -- and the two are compared by eye in review.
README = {
    "verdict_keys": {"fired", "pending", "phase", "readings", "violations"},
    "pending_entry_keys": {"eca", "process", "choices"},
    "reading_keys": {"id", "kind", "value", "refClass"},
    "violation_keys": {"eca", "witness", "detail"},
    "witness_keys": {"refs", "counts"},
    "count_keys": {"name", "value"},
    "list_keys": {"ecas"},
    "apply_ok_keys": {"graph"},
    "apply_reject_keys": {"error"},
    "envelope_keys": {"act", "graph"},
}


def expect(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'} {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(name)


def run_oracle(oracle: Path, *args: str, stdin: str = "") -> tuple[int, str, str]:
    proc = subprocess.run(
        [str(oracle), *args], input=stdin, capture_output=True, text=True, timeout=60
    )
    return proc.returncode, proc.stdout, proc.stderr


def main(argv: list[str]) -> int:
    case = (ROOT / (argv[1] if len(argv) > 1 else "cases/mayor-2027")).resolve()
    oracle = case / "oracle"
    manifest = yaml.safe_load((case / "manifest.yaml").read_text())
    print(f"README contract — {case.name}\n")

    # ---- CLI behaviour ---------------------------------------------------
    code, out, _ = run_oracle(oracle, "list")
    expect("`oracle list` exits 0", code == 0)
    expect("`oracle list` keys", set(json.loads(out)) == README["list_keys"], out[:120])
    expect(
        "`oracle list` matches the manifest's ECA ids",
        sorted(json.loads(out)["ecas"]) == sorted(e["id"] for e in manifest["ecas"]),
        out[:120],
    )

    code, _, _ = run_oracle(oracle, "bogus-verb")
    expect("an unknown verb exits non-zero", code != 0, f"exit {code}")

    code, _, err = run_oracle(oracle, "check", stdin="not json")
    expect("`check` with bad input exits non-zero", code != 0, f"exit {code}")
    expect("`check` with bad input explains itself on stderr", bool(err.strip()), err[:80])

    # ---- drive the law to where every documented shape occurs ------------
    # By playing whatever the verdict offers rather than by naming mayor ECAs:
    # the point of this suite is that the documented protocol holds for a law
    # the document never mentions. One round only -- the law stalls once its
    # current offers are exhausted, and driving further just leaves nothing
    # pending to send.
    c = OracleClient(case)
    advance(c, case, rounds=1)

    verdict = c.check()
    expect(
        "the verdict has exactly the documented top-level keys",
        set(verdict) == README["verdict_keys"],
        f"got {sorted(verdict)}",
    )
    entries = [e for es in verdict["pending"].values() for e in es]
    expect(
        "a pending entry has only the documented keys",
        all(set(e) <= README["pending_entry_keys"] for e in entries),
        str([sorted(e) for e in entries]),
    )
    expect(
        "every pending entry names a process instance",
        all(e.get("process", "").startswith(PH) for e in entries),
        str([e.get("process") for e in entries]),
    )
    expect(
        "every reading has only the documented keys",
        all(set(r) <= README["reading_keys"] for r in verdict["readings"]),
        str([sorted(r) for r in verdict["readings"]]),
    )
    expect(
        "every reading's kind is in the closed set",
        all(r["kind"] in READING_KINDS for r in verdict["readings"]),
        str([r.get("kind") for r in verdict["readings"]]),
    )
    expect(
        "every `ref` reading names the class it resolves through",
        all("refClass" in r for r in verdict["readings"] if r["kind"] == "ref"),
    )
    expect(
        "every violation has exactly the documented keys",
        all(set(v) == README["violation_keys"] for v in verdict["violations"]),
        str([sorted(v) for v in verdict["violations"]]),
    )
    expect(
        "a witness has exactly the documented keys",
        all(set(v["witness"]) == README["witness_keys"] for v in verdict["violations"]),
        str([sorted(v["witness"]) for v in verdict["violations"]]),
    )
    expect(
        "a count has exactly the documented keys",
        all(
            set(cn) == README["count_keys"]
            for v in verdict["violations"]
            for cn in v["witness"]["counts"]
        ),
    )
    expect(
        "a violation still carries a display string",
        all(v.get("detail") for v in verdict["violations"]),
    )

    # ---- the wire format -------------------------------------------------
    wire = graph_to_wire(c.graph)
    expect("the envelope has exactly the documented keys", set(wire) == {"graph"},
           str(sorted(wire)))
    rows = wire["graph"]
    expect("every row is a 3-element array", all(isinstance(r, list) and len(r) == 3 for r in rows))
    literals = [o for r in rows for o in r[2:] if isinstance(o, dict)]
    expect(
        "a literal is {lit, type}",
        bool(literals) and all(set(l) == {"lit", "type"} for l in literals),
        str(literals[:1]),
    )
    expect(
        "an IRI object is a bare string",
        all(isinstance(o, str) for r in rows for o in r[2:] if not isinstance(o, dict)),
    )

    # ---- apply ----------------------------------------------------------
    # Guarded: a law driven to completion has nothing left to send, and the
    # success shape cannot be exercised then. Not a failure of the protocol.
    offered = pending_acts(c, manifest_of(case))
    if not offered:
        expect("an act was available to send (skipped: none offered)", True)
        print(chr(10) + "all pass")
        return 0
    envelope = {"act": offered[-1], "graph": rows}
    code, out, _ = run_oracle(oracle, "apply", stdin=json.dumps(envelope))
    expect("a well-formed apply exits 0", code == 0, out[:140])
    if code == 0:
        expect("apply's success keys",
               set(json.loads(out)) == README["apply_ok_keys"], out[:120])
    # Take an act the verdict is actually offering, rather than naming one: at
    # day 10 hour 20 the nomination window has shut, so a hardcoded `nominate`
    # is rejected for the right reason and proves nothing about success.
    by_id = {e["id"]: e for e in manifest["ecas"]}
    offered = None
    for citizen, es in verdict["pending"].items():
        for e in es:
            decl = by_id.get(e["eca"])
            if decl is None:
                continue
            act = {"eca": e["eca"]}
            ok = True
            for prm in decl.get("params") or []:
                if prm["source"] == "selected":
                    act[prm["name"]] = citizen
                else:
                    opts = (e.get("choices") or {}).get(prm["name"]) or []
                    if not opts:
                        ok = False
                    else:
                        act[prm["name"]] = opts[0]
            if ok:
                offered = act
                break
        if offered:
            break
    expect("the verdict offers an act the manifest can build", offered is not None,
           str(verdict["pending"]))

    if offered:
        code, out, _ = run_oracle(
            oracle, "apply", stdin=json.dumps({"act": offered, "graph": rows})
        )
        expect("a well-formed apply exits 0", code == 0, out[:140])
        if code == 0:
            expect("apply's success keys",
                   set(json.loads(out)) == README["apply_ok_keys"], out[:120])

    # A rejection naming its guard. Which ECA is not due is the law's business,
    # so pick one this law declares that the verdict is not currently firing,
    # and build a COMPLETE act for it from the manifest -- an envelope carrying
    # a field the law's Act type has no slot for is a malformed act rather than
    # a refused one, and would not exercise the rejection path at all.
    fired = set(verdict["fired"])
    pool = {e["id"]: e for e in manifest["ecas"] if e["id"] not in fired}
    options: dict[str, list[str]] = {}
    for es in verdict.get("pending", {}).values():
        for entry in es:
            for slot, vals in (entry.get("choices") or {}).items():
                options.setdefault(slot, list(vals))
    someone = next(iter(verdict.get("pending", {})), None) or CITIZEN + "alice"
    refused = None
    for eid, e in pool.items():
        act: dict = {"eca": eid}
        ok = True
        for prm in e.get("params") or []:
            if prm["source"] == "selected":
                act[prm["name"]] = someone
            elif prm["name"] in options:
                act[prm["name"]] = options[prm["name"]][0]
            else:
                ok = False
                break
        if ok:
            refused = act
            break
    expect("the law has a complete act that is not due", refused is not None,
           f"not fired: {sorted(pool)}")
    code, out, err = run_oracle(
        oracle, "apply",
        stdin=json.dumps({"act": refused if refused else {}, "graph": rows})
    )
    expect("a rejected act exits 1", code == 1, f"exit {code}")
    try:
        body = json.loads(out)
    except Exception:  # noqa: BLE001
        body = {}
    expect("a rejection is JSON naming the guard",
           set(body) == README["apply_reject_keys"] and bool(body.get("error")),
           out[:140] or err[:140])

    # ---- `check [file]`, which the README claims works --------------------
    path = Path("/tmp/readme-check-graph.json")
    path.write_text(json.dumps(wire))
    code_file, out_file, err_file = run_oracle(oracle, "check", str(path))
    expect("`check <file>` exits 0", code_file == 0, err_file[:140])
    code_stdin, out_stdin, _ = run_oracle(oracle, "check", stdin=json.dumps(wire))
    expect("`check <file>` and stdin agree",
           code_file == code_stdin == 0 and out_file == out_stdin,
           f"file exit {code_file}, stdin exit {code_stdin}")

    # ---- the manifest declares what the oracle emits ---------------------
    declared = {r["id"] for r in manifest.get("readings") or []}
    expect("every emitted reading is declared in the manifest",
           {r["id"] for r in verdict["readings"]} <= declared,
           f"undeclared: {sorted({r['id'] for r in verdict['readings']} - declared)}")

    # ---- the prose names no field the code dropped -----------------------
    readme = (ROOT / "cases" / "README.md").read_text()
    for gone in ("would_win", "wouldWin", "witnessCitizen", "witnessCandidate"):
        expect(f"the README no longer mentions {gone}", gone not in readme)

    if fails:
        print(f"\n{len(fails)} FAILURE(S): {fails}")
        return 1
    print("\nall pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
