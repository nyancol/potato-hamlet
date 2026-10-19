/**
 * hamlet_check / hamlet_build / hamlet_freeze: exec wrappers over the repo's
 * own scripts. node:child_process only — no host imports — so the node
 * self-test calls these directly.
 *
 * The contract: the session judges drafts with the same gate CI runs, never
 * a reimplementation. Execution failure (missing uv, crash, timeout) is
 * thrown so pi reports a failed tool result; gate refusal (non-zero exit
 * WITH diagnostics) returns the findings as data. The two must never be
 * confused: a broken environment is not a refused draft.
 */

import { execFileSync } from "node:child_process";
import { parseGateOutput, type GateVerdict } from "./loop-lib.ts";

export interface ExecOpts {
	repoRoot: string;
	timeoutMs?: number;
}

const DEFAULT_TIMEOUT_MS = 300_000;

function run(
	script: string,
	args: string[],
	opts: ExecOpts,
): { exitCode: number; stdout: string; stderr: string } {
	try {
		const stdout = execFileSync("uv", ["run", "python", `tools/lawgen/${script}`, ...args], {
			cwd: opts.repoRoot,
			timeout: opts.timeoutMs ?? DEFAULT_TIMEOUT_MS,
			encoding: "utf8",
			maxBuffer: 16 * 1024 * 1024,
		});
		return { exitCode: 0, stdout: stdout as string, stderr: "" };
	} catch (e: unknown) {
		const err = e as { status?: number; stdout?: unknown; stderr?: unknown; message?: string; code?: string };
		if (typeof err.status === "number") {
			return {
				exitCode: err.status,
				stdout: typeof err.stdout === "string" ? err.stdout : "",
				stderr: typeof err.stderr === "string" ? err.stderr : "",
			};
		}
		// Never ran at all (bad cwd, missing binary): negative exit so the
		// parsers below read execFailed, never a refusal.
		return { exitCode: -1, stdout: "", stderr: `execution failed (${err.code ?? "spawn"}): ${err.message ?? e}` };
	}
}

/** Schema gate over the world fixture (check.py merges world + vocabulary). */
export function runHamletCheck(caseDir: string, opts: ExecOpts, full = false): GateVerdict {
	const args = full ? [caseDir] : ["--schema-only", caseDir];
	const r = run("check.py", args, opts);
	return parseGateOutput(r.exitCode, r.stdout, r.stderr);
}

/**
 * check.py is the only script with a canonical pass marker ("all checks
 * pass"). build and freeze speak exit codes only: 0 means done, non-zero
 * with output means refused naming something, non-zero with nothing means
 * the execution itself failed.
 */
export function parseExitCodeVerdict(exitCode: number, stdout: string, stderr: string): GateVerdict {
	const out = `${stdout}\n${stderr}`;
	const lines = out
		.split("\n")
		.map((l) => l.trim())
		.filter((l) => l.length > 0);
	if (exitCode === 0) {
		return { kind: "pass", detail: lines.slice(-3).join(" / ").slice(0, 300) || "exit 0" };
	}
	if (exitCode < 0 || lines.length === 0) {
		return { kind: "execFailed", error: lines.join(" / ").slice(0, 500) || `exit ${exitCode} with no output` };
	}
	return { kind: "refused", findings: lines.slice(0, 12) };
}

/** Compiled oracle build (needs the Lean toolchain; slow). */
export function runHamletBuild(caseDir: string, opts: ExecOpts): GateVerdict {
	const r = run("build_oracle.py", [caseDir], opts);
	return parseExitCodeVerdict(r.exitCode, r.stdout, r.stderr);
}

/** Freeze verify: frozen and unchanged, naming what moved otherwise. */
export function runHamletFreeze(caseDir: string, opts: ExecOpts): GateVerdict {
	const r = run("freeze.py", ["--verify", caseDir], opts);
	return parseExitCodeVerdict(r.exitCode, r.stdout, r.stderr);
}
