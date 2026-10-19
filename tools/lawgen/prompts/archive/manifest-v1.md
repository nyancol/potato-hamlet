# Step 1 prompt — manifest draft (v1)

You are drafting the `manifest.yaml` for a Potato Hamlet law artefact set.
You receive the reviewed `ontology.ttl` and `rules.lean`. Output ONE YAML
file to stdout and nothing else.

## Fixed contract

- Fields: `case` (directory name), `freeze: null` (never invent a hash;
  the review gate sets it), `ontology` (ttl filename), `oracle` (binary
  filename in the case directory, written by `tools/lawgen/build_oracle.py`;
  never null in a frozen set — the loader resolves it for subprocess use),
  `time` (cycle_days,
  announce_minus, prepare_minus, polls_open, polls_close), `ecas` (list
  of `id`, `eca_process` = GFO Process class short name, `label`,
  `message` with `{holder}`/`{citizen}` placeholders, `modality` =
  should|must|may preserved from the source text).
- ECA `id`s MUST equal the Lean ECA ids exactly; the review gate refuses
  mismatches against oracle `list`. Labels/messages are display-only.
- No rule truth here: conditions, holders, winners live in Lean.

## Output

Raw YAML only. No markdown fences, no explanations.
Ontology follows after `---ONTOLOGY---`, Lean after `---LEAN---`.
