"""Strict validator for the clarification-loop report handoff.

The extractor's report is a SEPARATE structured value -- the three draft files
plus a list of {step, why-ungroundable} -- never a fenced block inside a draft.
Free-text output is not a handoff: a pass that phrases uncertainty politely
must not parse as converged. So this validator is strict by design: it accepts
exactly the schema shape and rejects everything else with a non-zero exit.

Usage:
  uv run python tools/lawgen/validate_report.py report.json
  uv run python tools/lawgen/validate_report.py --stdin < report.json
  echo '{"report": []}' | uv run python tools/lawgen/validate_report.py --stdin

Exit 0 on a well-formed report (including the empty, converged one), 1 on any
violation. Violations include: unparseable JSON, a top-level shape that is not
{"report": [...]}, entries missing `step` or `why-ungroundable`, empty or
non-string fields, extra keys, and anything that looks like a draft file with
a fenced report block smuggled inside it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "framework" / "clarification-report.schema.json"

ALLOWED_TOP_KEYS = {"report"}
ALLOWED_ENTRY_KEYS = {"step", "why-ungroundable"}


def validate(data) -> list[str]:
    """Return a list of violations; empty means the report is well-formed."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"report must be a JSON object, got {type(data).__name__}"]
    extra = set(data) - ALLOWED_TOP_KEYS
    if extra:
        errors.append(f"unexpected top-level keys: {sorted(extra)} (only 'report' is allowed)")
    if "report" not in data:
        return errors + ["missing required key 'report'"]
    items = data["report"]
    if not isinstance(items, list):
        return errors + [f"'report' must be a list, got {type(items).__name__}"]
    for i, entry in enumerate(items):
        where = f"report[{i}]"
        if not isinstance(entry, dict):
            errors.append(f"{where} must be an object, got {type(entry).__name__}")
            continue
        extra_keys = set(entry) - ALLOWED_ENTRY_KEYS
        if extra_keys:
            errors.append(f"{where} has unexpected keys: {sorted(extra_keys)}")
        for key in ("step", "why-ungroundable"):
            if key not in entry:
                errors.append(f"{where} is missing required key {key!r}")
            elif not isinstance(entry[key], str):
                errors.append(f"{where}.{key} must be a string, got {type(entry[key]).__name__}")
            elif not entry[key].strip():
                errors.append(f"{where}.{key} must not be empty")
    return errors


def looks_like_draft_with_fenced_block(text: str) -> bool:
    """Catch the shape task 0.1 rejected: a draft file with a report fenced inside."""
    markers = ("```", "ontology.ttl", "population.ttl", "rules.lean", "@prefix")
    return "```" in text and any(m in text for m in markers[1:])


def main(argv: list[str]) -> int:
    if "--stdin" in argv:
        text = sys.stdin.read()
        source = "<stdin>"
    elif len(argv) >= 2:
        source = argv[1]
        try:
            text = Path(source).read_text()
        except OSError as e:
            print(f"error: cannot read {source}: {e}", file=sys.stderr)
            return 1
    else:
        print(__doc__)
        return 2

    if looks_like_draft_with_fenced_block(text):
        print(f"{source}: rejected: a draft file with a fenced report block is not a report -- "
              f"the report is a separate structured value", file=sys.stderr)
        return 1
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"{source}: rejected: not parseable JSON: {e}", file=sys.stderr)
        return 1

    # A bare string (free text) parses as JSON but is not a report.
    errors = validate(data)
    if errors:
        for e in errors:
            print(f"{source}: rejected: {e}", file=sys.stderr)
        return 1
    n = len(data["report"])
    print(f"{source}: ok ({n} question(s){', converged' if n == 0 else ''})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
