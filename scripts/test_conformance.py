"""Pending/apply conformance: every pending act applies clean, non-pending rejects.

Acts are derived from the manifest's DECLARED parameters plus the choices the
verdict supplies, never from a hardcoded table — that is the point: if the
driver needed per-law knowledge to build an act, the declarations would not be
doing their job. Guards against `pendingOf`/`apply` drift (design risk 1).

Usage:
  uv run python scripts/test_conformance.py artefacts/mayor-2027
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from potato_hamlet.oracle import OracleClient, OracleRejected  # noqa: E402

P = "https://potato-hamlet.example/ontology/"
A, B, C = P + "citizen/alice", P + "citizen/bob", P + "citizen/cara"


def act_from_declaration(eca: dict, pending_choices: dict) -> dict:
    """Build an act from the manifest's declared parameters.

    A parameter sourced `selected` binds to the acting citizen; one sourced
    `choices` takes the first option the verdict offered. Nothing here knows
    which law it is driving.
    """
    act: dict = {"eca": eca["id"]}
    for param in eca.get("params") or []:
        name, source = param["name"], param["source"]
        if source == "selected":
            act[name] = pending_choices["selected"]
        elif source == "choices":
            options = pending_choices.get(name) or []
            if not options:
                raise ValueError(f"{eca['id']}.{name} is sourced 'choices' but no options were offered")
            act[name] = options[0]
    return act


def main(argv: list[str]) -> int:
    case = (ROOT / (argv[1] if len(argv) > 1 else "artefacts/mayor-2027")).resolve()
    manifest = yaml.safe_load((case / "manifest.yaml").read_text())
    by_id = {e["id"]: e for e in manifest["ecas"]}
    fails: list[str] = []

    def expect(name: str, cond: bool, detail: str = ""):
        print(("PASS " if cond else "FAIL ") + name + (f" ({detail})" if detail and not cond else ""))
        if not cond:
            fails.append(name)

    def fresh() -> OracleClient:
        return OracleClient(case)

    def entry_choices(entry: dict) -> dict:
        """Choice slots the verdict offers for one pending entry."""
        return entry.get("choices") or {}

    # Every ECA declares its params, so an act can always be built.
    missing = [i for i, e in by_id.items() if "holder_role" not in e or "params" not in e]
    expect("every ECA declares holder_role and params", not missing, str(missing))

    def announced_and_nominated(c: OracleClient):
        """Announce, then take every citizen's nomination.

        The graph starts empty, so a scenario must reach its own state by
        playing acts — the old fixtures seeded `candidates` directly, which
        the graph cannot do. Each scenario stops at the last act it is meant
        to exercise, so the act under test is still pending.
        """
        c.set_time(0)
        c.apply({"eca": "announce"})
        for who in (A, B, C):
            c.apply({"eca": "nominate", "citizen": who})

    def ballots_exist(c: OracleClient):
        announced_and_nominated(c)
        c.set_time(9)
        c.apply({"eca": "prepare"})

    scenarios = [
        ("announce-day", 0, 10, ["announce", "nominate"], None),
        ("nominate-window", 5, 10, ["nominate"], None),
        ("prepare-day", 9, 10, ["prepare"], announced_and_nominated),
        ("polls-open", 10, 12, ["vote"], ballots_exist),
        ("polls-closed", 10, 20, ["vote", "count"], ballots_exist),
        ("count-due", 11, 10, ["count"], ballots_exist),
    ]
    for name, day, hour, expect_fired, setup in scenarios:
        c = fresh()
        if setup is not None:
            setup(c)
        c.set_time(day, hour)
        v = c.check()
        expect(f"{name}: fires {expect_fired}", sorted(v["fired"]) == sorted(expect_fired),
               str(v["fired"]))
        # Every act the verdict offers as pending applies cleanly.
        offered = 0
        for citizen, entries in v["pending"].items():
            for entry in entries:
                # Each pending entry names its ECA and the choices available now.
                eca_id = entry["eca"] if isinstance(entry, dict) else entry
                eca = by_id.get(eca_id)
                if eca is None:
                    continue
                choices = {"selected": citizen, **entry_choices(entry)}
                try:
                    act = act_from_declaration(eca, choices)
                    offered += 1
                    c.apply(act)
                except (OracleRejected, ValueError) as e:
                    expect(f"{name}: apply {eca_id}", False, str(e))
                    break
        expect(f"{name}: {offered} pending acts all apply", offered > 0, "no acts offered")

    # Representative non-pending acts reject with a named guard.
    c = fresh()
    c.set_time(10, 20)  # polls closed at 19
    before = c.subjects()
    rejects = [
        ("vote-when-closed", {"eca": "vote", "voter": A, "candidate": B}, "polls closed"),  # hour 20
        ("nominate-when-closed", {"eca": "nominate", "citizen": A}, "registry closed"),
        ("proclaim-with-no-candidacy", {"eca": "proclaim"}, "no candidates"),
        ("announce-when-not-due", {"eca": "announce"}, "not due"),
    ]
    for name, act, fragment in rejects:
        try:
            c.apply(act)
            expect(f"{name} rejects", False, "act was accepted")
        except OracleRejected as e:
            expect(f"{name} rejects", fragment in str(e), str(e))
    expect("rejections leave the graph unchanged", c.subjects() == before, "graph changed")

    print(f"\n{'all pass' if not fails else f'{len(fails)} FAILURES: {fails}'}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
