"""Build the compiled oracle exe for a law case.

Copies cases/<case>/rules.lean to lean/RulesCase.lean
(single source of truth stays the case file), registers the oracle exe in
a generated lakefile target, and runs `lake build`.

Usage:
  uv run python tools/lawgen/build_oracle.py cases/mayor-2027
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LEAN_DIR = ROOT / "lean"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    case = (ROOT / argv[1]).resolve()
    name = case.name.replace("-", "_")
    rules = case / "rules.lean"
    if not rules.exists():
        print(f"error: no rules.lean in {case}", file=sys.stderr)
        return 1
    shutil.copy(rules, LEAN_DIR / "RulesCase.lean")
    # RulesCase must be a lake module: register a lib target if missing.
    lakefile = (LEAN_DIR / "lakefile.toml").read_text()
    if 'name = "RulesCase"' not in lakefile:
        with open(LEAN_DIR / "lakefile.toml", "a") as f:
            f.write('\n[[lean_lib]]\nname = "RulesCase"\n')
    # One oracle exe only: rebuild it against the current case's RulesCase.
    # (Lake forbids two exes sharing root OracleMain; per-case binaries are
    # produced by building one case at a time and copying the binary out.)
    exe_name = "oracle"
    lakefile = (LEAN_DIR / "lakefile.toml").read_text()
    if '\nname = "oracle"\n' not in lakefile and 'name = "oracle"' not in lakefile:
        # drop any stale per-case exe stanzas sharing root OracleMain
        lines = lakefile.splitlines(keepends=True)
        out, skip = [], False
        for i, ln in enumerate(lines):
            if ln.strip() == "[[lean_exe]]":
                block = "".join(lines[i:i + 3])
                if 'root = "OracleMain"' in block:
                    skip = True
                    continue
            if skip:
                if ln.strip().startswith("root =") or ln.strip().startswith("name ="):
                    if ln.strip().startswith("root ="):
                        skip = False
                    continue
            out.append(ln)
        (LEAN_DIR / "lakefile.toml").write_text("".join(out))
        with open(LEAN_DIR / "lakefile.toml", "a") as f:
            f.write('\n[[lean_exe]]\nname = "oracle"\nroot = "OracleMain"\n')
    proc = subprocess.run(["lake", "build", exe_name], cwd=LEAN_DIR,
                          capture_output=True, text=True, timeout=900)
    print(proc.stdout[-3000:] if len(proc.stdout) > 3000 else proc.stdout, end="")
    if proc.returncode != 0:
        print(proc.stderr[-5000:], file=sys.stderr)
        return 1
    built = LEAN_DIR / ".lake" / "build" / "bin" / exe_name
    # Per-case binary: copy out next to the case so flavors coexist.
    dest = case / exe_name
    shutil.copy(built, dest)
    dest.chmod(0o755)
    print(f"oracle built: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
