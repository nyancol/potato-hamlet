# Step 1 prompt — manifest draft (v2)

You are drafting the `manifest.yaml` for a Potato Hamlet law artefact set.
You receive the reviewed `ontology.ttl` and `rules.lean`. Output ONE YAML
file to stdout and nothing else.

## Fixed contract

- Fields: `case` (directory name), `freeze: null` (never invent a hash;
  the review gate sets it), `ontology` (ttl filename), `population`
  (seed ttl filename in the case directory, same RDF syntax as the schema),
  `oracle` (binary filename in the case directory, written by
  `tools/lawgen/build_oracle.py`; never null in a frozen set — the loader resolves
  it for subprocess use), `time` (cycle_days,
  announce_minus, prepare_minus, polls_open, polls_close), `ecas` (list
  of `id`, `eca_process` = GFO Process class short name, `holder_role`,
  `params`, `label`,
  `message` with `{holder}`/`{citizen}` placeholders, `modality` =
  should|must|may preserved from the source text), and `readings`.
- ECA `id`s MUST equal the Lean ECA ids exactly; the review gate refuses
  mismatches against oracle `list`. Labels/messages are display-only.
- No rule truth here: conditions, holders, winners live in Lean.

## Per-ECA display declarations

These let a law-agnostic consumer build the act and its UI without any
per-law code. Declare them for EVERY ECA.

- `holder_role`: the GFO Role class short name the duty attaches to. It MUST
  be a Role the ontology declares as participating in that ECA's
  `eca_process`; the gate checks this. (Do NOT encode *who* holds the duty
  when no office is filled — that rule lives in Lean.)
- `params`: a list, empty when the ECA takes no arguments. Each entry has
  - `name`: the exact JSON wire field the oracle's `Act` expects
    (e.g. `citizen`, `voter`, `candidate`) — MUST match the Lean parameter
    name, not the message placeholder;
  - `role`: the GFO Role class this parameter binds to;
  - `source`: exactly one of
    - `selected` — auto-bound to the citizen the user has selected; or
    - `choices` — the oracle supplies the available options at check time and
      the consumer renders a picker.
  Typical shape: a self-nomination takes `{name: citizen, role:
  VoterRole, source: selected}`; a vote takes `{name: voter, ... source:
  selected}` plus `{name: candidate, role: CandidateRole, source: choices}`.

## Readings block

Declare a template for every result the oracle emits in its `readings` list,
so the guide can render it without parsing anything. The oracle reports a
reading as `{id, kind, value}` where `kind` is `decimal`, `ref`, or `flag`.
Each entry here gives:
  - `id`: the reading id the oracle emits;
  - `class`: the ontology class a `ref` reading points at (omit otherwise);
  - `label`: short display name;
  - `template`: the sentence, using `{value}`, `{of}`, `{label}` placeholders
    (where `{label}` is a referenced individual's resolved name).

Declare only readings this law can actually emit. A law with no result of a
shape omits it; never declare a placeholder for a reading that never fires.

## Clarification loop — report what you cannot ground

This draft is one pass of an iterative loop, not a one-shot delivery. Alongside
the YAML file you return a SEPARATE structured report listing every step the
law text requires that no declared object, capability, or action accounts for —
a duty whose mechanism nothing in `framework/physical.ttl` qualifies an object
for, or that no world individual performs. Each entry is `{step, why-ungroundable}`:
quote the step, then say which object, capability, or action is missing.

The report is a separate value conforming to
`framework/clarification-report.schema.json`. It is NEVER a fenced block inside
the draft: the draft files go into the freeze hash verbatim, so anything left
inside them becomes part of the frozen TBox. A validator rejects anything but
the strict shape — free text and fenced blocks do not parse as converged.

Where a declared capability DOES account for the step, proceed and declare
against it, and do not ask. A holder, param, or reading over a capability the
shared vocabulary declares is an ordinary declaration, not a question. The
threshold stated only negatively produces performative reporting — a
well-covered law asks nothing.

Do NOT invent a mechanism in order to avoid reporting a step. An invented class
is checkable and a concealed guess is not: a name wired into a superclass,
domain, or range fails the gate by name, while a guess hidden inside a
plausible declaration builds, passes, and reads as if the text determined it.

## Output

Raw YAML only. No markdown fences, no explanations.
Ontology follows after `---ONTOLOGY---`, Lean after `---LEAN---`.
