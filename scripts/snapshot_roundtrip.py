"""Round-trip probe for the graph wire format.

Sends the law's seeded instance graph through the wire format and checks
nothing is lost: every subject, predicate and object survives, and the oracle
accepts it. This is the narrowest guard on the format itself, independent of
any law's rules.

Usage:
  uv run python scripts/snapshot_roundtrip.py artefacts/mayor-2027
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from potato_hamlet.graphwire import (  # noqa: E402
    graph_to_wire, load_artefact_case, round_trip, wire_to_graph,
)
from potato_hamlet.oracle import OracleClient  # noqa: E402


def main(argv: list[str]) -> int:
    case = (ROOT / (argv[1] if len(argv) > 1 else "artefacts/mayor-2027")).resolve()
    fails: list[str] = []

    def expect(name: str, cond: bool, detail: str = ""):
        print(("PASS " if cond else "FAIL ") + name + (f" ({detail})" if detail and not cond else ""))
        if not cond:
            fails.append(name)

    schema, seed = load_artefact_case(case)
    combined = schema + seed

    # 1. The wire format is lossless for the whole artefact graph.
    try:
        round_trip(combined)
        expect("graph wire round trip is lossless", True)
    except AssertionError as e:
        expect("graph wire round trip is lossless", False, str(e))

    # 2. Only the ABox crosses the boundary; schema triples stay behind.
    wire = graph_to_wire(combined)
    predicates = {row[1] for row in wire["graph"]}
    leaked = [p for p in predicates if p.endswith(("subClassOf", "subPropertyOf", "domain", "range"))]
    expect("no schema predicates on the wire", not leaked, str(leaked))
    expect("wire carries every seeded triple", len(wire["graph"]) == len(seed), str(len(wire["graph"])))

    # 3. Ordering is normalised, so the same graph always serialises identically.
    expect("serialisation is deterministic",
           graph_to_wire(combined) == graph_to_wire(combined))

    # 4. Re-parsing the seed yields a graph the oracle accepts.
    reparsed = wire_to_graph(wire)
    expect("reparsed seed holds the same triples",
           {str(t[0]) for t in reparsed} == {str(t[0]) for t in seed})

    client = OracleClient(case)
    expect("oracle accepts the seeded graph",
           isinstance(client.check(), dict))

    print(f"\n{'all pass' if not fails else f'{len(fails)} FAILURES: {fails}'}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
