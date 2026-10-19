-- Oracle CLI for a law case: cold-spawn, stateless JSON over stdin/stdout.
-- Build wiring: tools/lawgen/build_oracle.py copies cases/<case>/rules.lean
-- to lean/RulesCase.lean and compiles OracleMain.lean against it.
-- Protocol (framework-fixed):
--   oracle list                                  -> {"ecas": [...]}
--     (must equal manifest eca ids)
--   oracle check < graph.json (stdin or argv[2])  -> verdict JSON, exit 0.
--     The knowledge graph IS the snapshot: the input is the ABox as typed
--     instance triples, and the law's `snapshotOf` derives its own state.
--   oracle apply < {"act": ..., "graph": ...}    -> new graph JSON, exit 0;
--     on rejection -> {"error": reason}, exit 1. The returned graph replaces
--     the consumer's stored one wholesale.
-- Bad input -> stderr + exit non-zero.
import RulesCase
import Lean.Data.Json

open Lean

def cmdList : IO UInt32 := do
  IO.println (Json.mkObj [("ecas", toJson ecaIds)]).compress
  return 0

/-- The graph JSON, from a file argument or stdin.

    `args` is the full argv, so for `check <file>` the verb is at index 0 and
    the PATH IS AT INDEX 1. The pattern this replaces looked for it at index 2
    and needed four arguments to match, so `check <file>` fell through to an
    empty stdin and reported a parse error at offset 0 -- while the usage
    string advertised the argument as working. -/
def readInput (args : List String) : IO String := do
  match args with
  | _ :: path :: _ => IO.FS.readFile path
  | _ => do
    let stdin ← IO.getStdin
    stdin.readToEnd

def parseGraph (input : String) : Except String Graph :=
  match Json.parse input with
  | .error e => Except.error s!"parse error: {e}"
  | .ok j =>
    match FromJson.fromJson? (α := GraphEnvelope) j with
    | .error e => Except.error s!"bad graph: {e}"
    | .ok env => .ok env.graph

def cmdCheck (args : List String) : IO UInt32 := do
  let input ← readInput args
  match parseGraph input with
  | .error e => IO.eprintln e; return 1
  | .ok g =>
    IO.println (ToJson.toJson (evaluate (snapshotOf g))).compress
    return 0

def cmdApply : IO UInt32 := do
  let stdin ← IO.getStdin
  let input ← stdin.readToEnd
  match Json.parse input with
  | .error e => IO.eprintln s!"parse error: {e}"; return 1
  | .ok j =>
    match j.getObjVal? "act" >>= FromJson.fromJson? (α := Act) with
    | .error e => IO.eprintln s!"bad act: {e}"; return 1
    | .ok act =>
      match j.getObjVal? "graph" >>= FromJson.fromJson? (α := Graph) with
      | .error e => IO.eprintln s!"bad graph: {e}"; return 1
      | .ok g =>
        match applyGraph act g with
        | .ok g' =>
          IO.println (ToJson.toJson (GraphEnvelope.mk g')).compress; return 0
        | .error reason =>
          IO.println (Json.mkObj [("error", toJson reason)]).compress; return 1

def main (args : List String) : IO UInt32 := do
  match args[0]? with
  | some "list" => cmdList
  | some "check" => cmdCheck args
  | some "apply" => cmdApply
  | cmd => IO.eprintln s!"usage: oracle (list|apply|check [file)]; got: {cmd}"; return 2
