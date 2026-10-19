#!/bin/sh
# Credential-gated end-to-end for the real /draft-law command.
#
# Skips cleanly with no model credential (exit 0). PI_E2E_FORCE_SKIP=1
# exercises the skip branch on a keyed machine. Otherwise drives two
# headless runs and asserts the exit-code contract whatever the model does:
# exit 0 if and only if the final report is empty AND the gate passes;
# questions asked at most once per run.
#
# Records the installed pi host version alongside so handoff shape
# regressions can be traced across host upgrades.
#
# Usage: bash pi/selftest/e2e.sh [--out dir]
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
OUTBASE="${2:-/tmp/opencode/pi-e2e}"

if [ -n "$PI_E2E_FORCE_SKIP" ]; then
  echo "SKIP: pi e2e (PI_E2E_FORCE_SKIP set, no model touched)"
  exit 0
fi

has_credential() {
  for v in ANTHROPIC_API_KEY OPENAI_API_KEY GOOGLE_GENERATIVE_AI_KEY GEMINI_API_KEY OPENROUTER_API_KEY; do
    eval "val=\${$v}"
    if [ -n "$val" ]; then return 0; fi
  done
  for p in openrouter anthropic openai google; do
    if pi auth check --provider "$p" 2>/dev/null | grep -q ready; then return 0; fi
  done
  return 1
}

if ! has_credential; then
  echo "SKIP: pi e2e (no model credential; contract tests in pi/selftest/run.sh are the floor)"
  exit 0
fi

rm -rf "$OUTBASE"
mkdir -p "$OUTBASE"

# Record the installed pi host version so handoff shape regressions can be
# traced across host upgrades.
pi --version 2>/dev/null > "$OUTBASE/host-version.txt" || echo "pi-version-unknown" > "$OUTBASE/host-version.txt"
echo "pi host: $(cat "$OUTBASE/host-version.txt")"
cat > "$OUTBASE/answers.json" <<'EOF'
{
  "They must put these papers in the mailbox of each citizen": "The mayor delivers into each mailbox during the preparation day",
  "one paper per candidate for each citizen, so everyone can choose": "Ballots are made on the sheets owned by each citizen, one per candidate"
}
EOF

run_loop() {
  name="$1"; extra="$2"
  # Word-splitting $extra on purpose (optional flags); the if guards set -e.
  # Debug trace on: branch shapes per pass go to the run log (stderr).
  # shellcheck disable=SC2086
  if PI_DRAFT_LAW_DEBUG=1 pi -a -p "/draft-law cases/mayor-2027 --out $OUTBASE/$name --max-passes 2 $extra" > "$OUTBASE/$name.log" 2>&1; then
    echo 0
  else
    echo $?
  fi
}

check_run() {
  name="$1"; code="$2"
  uv run python - "$OUTBASE/$name" "$code" "$ROOT" "$OUTBASE/$name.log" <<'PYEOF'
import json, re, subprocess, sys
outdir, code, root, logpath = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
report = json.load(open(f"{outdir}/report.json"))["report"]
fails = []
outstanding = report is None or len(report) != 0
if code == 0 and outstanding:
    fails.append(f"exit 0 with {'no structured report' if report is None else f'{len(report)} entries outstanding'}")
if code != 0 and not outstanding:
    # consistent only if the gate refused the converged draft: re-run it
    p = subprocess.run(["uv", "run", "python", "tools/lawgen/check.py", "--schema-only", outdir],
                       capture_output=True, text=True, cwd=root)
    if p.returncode == 0:
        fails.append("exit non-zero but report empty and gate passes")
# No step asked twice: the asked-set is memory-only by design (no record of
# the exchange is kept), so this reads the debug trace, not a file.
log = open(logpath).read()
asked_runs = re.findall(r"\[draft-law debug\] asked so far: (\[.*?\])", log)
seen: set[str] = set()
for run in asked_runs:
    for step in json.loads(run):
        if step in seen:
            fails.append(f"a step was asked twice: {step}")
        seen.add(step)
if fails:
    print(f"FAIL {outdir}: " + "; ".join(fails))
    sys.exit(1)
n = "none (no handoff)" if report is None else str(len(report))
print(f"PASS {outdir}: exit {code} consistent with {n} outstanding")
PYEOF
}

code_a=$(run_loop "A-unanswered" "")
check_run "A-unanswered" "$code_a"
code_b=$(run_loop "B-seeded" "--answers $OUTBASE/answers.json")
check_run "B-seeded" "$code_b"
echo "e2e done."
