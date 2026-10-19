# Potato Hamlet drafting package for pi

Clarification-loop drafting for Potato Hamlet laws. `/draft-law` owns the
loop as code; the report tool binds the project-owned schema; wrappers call
the repo's own gate. Contracts: `tools/lawgen/clarification-loop-pi-contract.md`.

## Layout

```text
pi/
├── package.json            # plain directory package, no runtime deps
├── extensions/
│   └── drafting/           # multi-file extension (subdirectory with index.ts)
│       ├── index.ts        # factory: registers everything below
│       ├── loop-lib.ts     # pure loop decisions (no imports; node-testable)
│       ├── loop-state.ts   # loop record shared by command and guard
│       ├── report-core.ts  # report_ungroundable_steps schemas + execute
│       ├── report-tool.ts  # defineTool glue
│       ├── gate-core.ts    # hamlet_check/build/freeze exec + verdicts
│       ├── gate-tools.ts   # defineTool glue
│       ├── draft-law.ts    # /draft-law command + loop wiring
│       └── settle-guard.ts # agent_before_settle backstop
├── skills/drafting/SKILL.md  # guidance only; never drives iteration
└── selftest/               # NOT loaded by pi (non-conventional dir)
    ├── run.ts              # credential-free checks, run with plain node
    └── e2e.sh              # credential-gated pi -p end-to-end (skips cleanly)
```

## Install (project-local)

```bash
pi install ./tools/pi --local --approve
```

This records the package in `.pi/settings.json` (project trust). `--approve`
covers the install itself; the first interactive run additionally asks for
project trust (a one-time grant pi remembers for this checkout). Non-interactive
runs grant it per invocation instead:

```bash
pi -a -p "/draft-law cases/mayor-2027 --answers answers.json --out /tmp/loop-out"
```

Verify the install with no model involved:

```bash
pi -a -p "/draft-law cases/no-such-case"   # handler error, exit 1
```

Then run `/draft-law` inside pi:

```text
/draft-law cases/mayor-2027 --answers /tmp/answers.json --out /tmp/loop-out
```

Flags: `--answers file` (step→answer JSON, stands in for the author),
`--out dir` (default `<case>/drafts/pi-loop`), `--max-passes n` (default 5),
`--gate-mode schema|full` (default schema).

## Self-test (no credential)

```bash
node pi/selftest/run.ts
```

`NODE_PATH` must resolve `typebox` (it ships inside pi's install; the
runner prints the exact export if it cannot find it). Cross-checks the
report validator against `tools/lawgen/validate_report.py` over shared fixtures,
exercises the tool executes and gate wrappers, and asserts the skill holds
no loop-driving instructions.

## End-to-end (credential required)

```bash
bash pi/selftest/e2e.sh
```

Skips cleanly with no model credential; drives the real `/draft-law`
command with scripted answers when keyed.
