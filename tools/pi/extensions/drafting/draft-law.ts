/**
 * /draft-law: the clarification loop as code.
 *
 * Two paths, one decision core (loop-lib.ts):
 *
 * - Interactive (hasUI): the handler KICKS OFF (setup + first pass) and every
 *   pass completion is consumed by the agent_end driver below, which
 *   validates, asks, and triggers the next pass. Turn-pumping follows pi's
 *   own grain (extension code starts turns via sendMessage({triggerTurn}),
 *   reacts in agent_end) — the -p probes proved queued messages never pump
 *   without the interactive event loop, so this path is TUI-only by
 *   necessity, not choice.
 * - Headless (-p, no UI): the handler runs the loop SYNCHRONOUSLY with nested
 *   streamSimple calls declaring the report tool, executing its calls
 *   in-handler via executeReport. No turn system involved at all — -p
 *   executes the input and exits, so anything queued would be abandoned.
 *   The handoff stays the tool call (strict-validated), never parsed prose.
 */
import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import type { ExtensionAPI, ExtensionCommandContext } from "@earendil-works/pi-coding-agent";
import type { Context as PiContext, Tool as PiTool } from "@earendil-works/pi-ai";
import { runHamletCheck } from "./gate-core.ts";
import {
	buildPassPrompt,
	decide,
	validateReport,
	type ClarificationReport,
} from "./loop-lib.ts";
import { consumePassId, endLoop, expectingPass, isRedelivery, loopState, noteSent, recordPass, resetLoop } from "./loop-state.ts";
import { executeReport, type ReportToolArgs } from "./report-core.ts";
import { ReportToolParams } from "./report-schemas.ts";

const REPORT_TOOL = "report_ungroundable_steps";
const PASS_TYPE = "draft-law-pass";
const DRAFT_FILES = ["ontology.ttl", "population.ttl", "rules.lean", "manifest.yaml"] as const;

interface DraftLawOptions {
	caseDir: string;
	answersFile: string | null;
	outDir: string | null;
	maxPasses: number;
	gateFull: boolean;
}

function parseArgs(raw: string): DraftLawOptions {
	const parts = raw.trim().split(/\s+/).filter((p) => p.length > 0);
	const opts: DraftLawOptions = { caseDir: "", answersFile: null, outDir: null, maxPasses: 5, gateFull: false };
	const positional: string[] = [];
	for (let i = 0; i < parts.length; i++) {
		const p = parts[i]!;
		if (p === "--answers") opts.answersFile = parts[++i] ?? null;
		else if (p === "--out") opts.outDir = parts[++i] ?? null;
		else if (p === "--max-passes") opts.maxPasses = Math.max(1, parseInt(parts[++i] ?? "5", 10) || 5);
		else if (p === "--gate-mode") opts.gateFull = (parts[++i] ?? "schema") === "full";
		else if (p.startsWith("--")) throw new Error(`draft-law: unknown flag ${p}`);
		else positional.push(p);
	}
	opts.caseDir = positional[0] ?? "";
	return opts;
}

/**
 * Stop with an error. In headless runs the message must ALSO become a
 * non-zero process exit: pi reports a throwing command as an "Extension
 * error" notice but still exits 0, so process.exitCode carries the
 * writes-and-exits contract. Never set in interactive mode, where the
 * session (and its later clean exit) outlives this command.
 */
function fail(hasUI: boolean, msg: string): never {
	if (!hasUI) {
		try {
			process.exitCode = 1;
		} catch {
			/* non-node host: the thrown message is all we have */
		}
	}
	throw new Error(msg);
}

interface PassHandoff {
	drafts: Record<string, string>;
	report: ClarificationReport | null;
	validity: string[] | null;
}

/** Latest report-tool handoff since branch[startLen], or a no-handoff record. */
function scanHandoff(branch: Array<unknown>, startLen: number): PassHandoff {
	for (let i = branch.length - 1; i >= startLen; i--) {
		const entry = branch[i] as {
			type?: string;
			message?: { role?: string; toolName?: string; details?: unknown; structuredContent?: unknown };
		};
		if (entry?.type !== "message") continue;
		const msg = entry.message;
		if (msg?.role !== "toolResult" || msg?.toolName !== REPORT_TOOL) continue;
		const details = (msg.details ?? {}) as {
			drafts?: Record<string, string>;
			report?: ClarificationReport["report"];
		};
		const structured = (msg.structuredContent ?? null) as ClarificationReport | null;
		const report: ClarificationReport | null =
			structured && Array.isArray(structured.report)
				? structured
				: Array.isArray(details.report)
					? { report: details.report }
					: null;
		return {
			drafts: details.drafts && typeof details.drafts === "object" ? details.drafts : {},
			report,
			validity: report ? validateReport(report) : null,
		};
	}
	return { drafts: {}, report: null, validity: null };
}

function writeOutputs(outDir: string, drafts: Record<string, string>, report: ClarificationReport | null): void {
	// Drafts plus the strict report only. Deliberately NO questions file and
	// NO answers file: the spec keeps no record of the exchange — an answer
	// belongs in the declarations it changed, not in a second place beside
	// them. The asked-set lives in memory for this run and dies with it.
	mkdirSync(outDir, { recursive: true });
	for (const name of DRAFT_FILES) {
		if (typeof drafts[name] === "string") writeFileSync(join(outDir, name), drafts[name] as string);
	}
	writeFileSync(join(outDir, "report.json"), JSON.stringify(report ?? { report: null }, null, 2) + "\n");
}

/** Seed the out dir with the full case (law.txt, oracle) minus drafts, so the gate sees a full set. */
function seedOutDir(caseAbs: string, outAbs: string): void {
	if (existsSync(outAbs)) rmSync(outAbs, { recursive: true, force: true });
	mkdirSync(outAbs, { recursive: true });
	const draftsAbs = join(caseAbs, "drafts");
	cpSync(caseAbs, outAbs, {
		recursive: true,
		filter: (src) => src === caseAbs || (!src.startsWith(draftsAbs + "/") && src !== draftsAbs),
	});
}

/** Build one fresh-pass prompt from disk render plus accumulated answers. */
function passPrompt(reextractNote: string | undefined): string {
	const rendered: Record<string, string> = {};
	for (const name of ["ontology.ttl", "rules.lean", "manifest.yaml"]) {
		rendered[name] = readFileSync(join(loopState.outDir, "render", `${name}.prompt.md`), "utf8");
	}
	return buildPassPrompt({
		rendered,
		answers: loopState.answersGiven,
		skillRef: join(loopState.repoRoot, "pi", "skills", "drafting", "SKILL.md"),
		reextractNote,
		maxPasses: loopState.maxPasses,
	});
}

/** Env-gated forensics: branch shapes per pass on stderr. Off by default; writes nothing. */
function debugBranch(tag: string, branch: Array<unknown>, startLen: number): void {
	if (process.env.PI_DRAFT_LAW_DEBUG !== "1") return;
	const summary = branch.slice(startLen).map((e) => {
		const entry = e as { type?: string; message?: { role?: string; toolName?: string; content?: unknown } };
		const msg = entry?.message;
		const content = Array.isArray(msg?.content) ? msg.content.map((c) => (c as { type?: string }).type).join("+") : typeof msg?.content;
		return { type: entry?.type, role: msg?.role, tool: msg?.toolName, content };
	});
	console.error(`[draft-law debug ${tag}] ${branch.length - startLen} new entries: ${JSON.stringify(summary).slice(0, 2000)}`);
}

/** Trigger the next pass and stamp its sequence number. Fire-and-forget by pi's design. */
function sendPass(pi: ExtensionAPI, branchLen: number, reextractNote: string | undefined): void {
	loopState.branchStartLen = branchLen;
	noteSent();
	pi.sendMessage(
		{ customType: PASS_TYPE, content: passPrompt(reextractNote), display: false },
		{ triggerTurn: true },
	);
}

/** Shared setup: validate, load bank, seed + render the out tree, reset state. */
function prepare(repoRoot: string, opts: DraftLawOptions, hasUI: boolean): { outAbs: string } {
	const caseAbs = resolve(repoRoot, opts.caseDir);
	if (!existsSync(join(caseAbs, "law.txt"))) {
		fail(hasUI, `draft-law: no law.txt in ${opts.caseDir}`);
	}
	const outAbs = resolve(repoRoot, opts.outDir ?? join(opts.caseDir, "drafts", "pi-loop"));
	const bank: Record<string, string> = {};
	if (opts.answersFile) {
		const parsed: unknown = JSON.parse(readFileSync(resolve(repoRoot, opts.answersFile), "utf8"));
		if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
			fail(hasUI, `draft-law: answers file must be a JSON object mapping step to answer`);
		}
		Object.assign(bank, parsed);
	}

	// Render into the out tree AFTER seeding it: seedOutDir wipes the out
	// dir, so rendering first would delete its own output.
	seedOutDir(caseAbs, outAbs);
	execFileSync("uv", ["run", "python", "tools/lawgen/redraft.py", opts.caseDir, "--json", join(outAbs, "render")], {
		cwd: repoRoot,
		timeout: 120_000,
		encoding: "utf8",
	});
	resetLoop({ repoRoot, caseDir: opts.caseDir, outDir: outAbs, bank, maxPasses: opts.maxPasses, gateFull: opts.gateFull });
	return { outAbs };
}

/** Kickoff (interactive): setup on disk, reset state, send pass one, return. */
async function kickoff(pi: ExtensionAPI, ctx: ExtensionCommandContext, repoRoot: string, opts: DraftLawOptions): Promise<void> {
	if (loopState.active) {
		ctx.ui.notify(
			`draft-law: a loop is already running (pass ${loopState.passIndex}, ${loopState.asked.length} step(s) asked). Settle or stop it before starting another.`,
			"warning",
		);
		return;
	}
	prepare(repoRoot, opts, ctx.hasUI);
	try {
		sendPass(pi, ctx.sessionManager.getBranch().length, undefined);
	} catch (e) {
		endLoop();
		fail(ctx.hasUI, `draft-law: could not start extraction pass: ${(e as Error).message}`);
	}
	ctx.ui.notify(`draft-law: loop started for ${opts.caseDir} — pass 1 extracting.`, "info");
}

/** One nested extraction pass (headless): model call with the report tool declared. */
async function nestedPass(
	ctx: ExtensionCommandContext,
	systemPrompt: string,
	userPrompt: string,
): Promise<{ toolCalls: Array<{ name: string; args: unknown }>; text: string }> {
	const model = ctx.model;
	if (!model) fail(false, "draft-law: no model selected for the headless run");
	const context: PiContext = {
		systemPrompt,
		messages: [{ role: "user", content: userPrompt, timestamp: Date.now() }],
		tools: [
			{
				name: REPORT_TOOL,
				description:
					"Hand over one extraction pass: the draft files plus the strict {step, why-ungroundable} " +
					"report. Call exactly once per pass. An empty report means the draft is converged.",
				parameters: ReportToolParams,
			} as PiTool,
		],
	};
	const toolCalls: Array<{ name: string; args: unknown }> = [];
	let text = "";
	const stream = ctx.modelRegistry.streamSimple(model, context, {});
	for await (const event of stream) {
		if (event.type === "text_delta") text += event.delta;
		else if (event.type === "toolcall_end") {
			if (event.toolCall.name === REPORT_TOOL) {
				toolCalls.push({ name: event.toolCall.name, args: event.toolCall.arguments });
			}
		} else if (event.type === "error") {
			const detail = typeof event.error === "string" ? event.error : JSON.stringify(event.error).slice(0, 300);
			fail(false, `draft-law: extraction model call failed (${event.reason}): ${detail}`);
		}
	}
	return { toolCalls, text };
}

/**
 * Headless loop (-p): synchronous passes, no turn system. Each pass is one
 * nested model call with the report tool declared; its calls execute
 * in-handler via executeReport. Bank answers stand in for the author; a step
 * with none stops the run. Exit 0 only on empty report plus passing gate.
 */
async function runHeadlessLoop(ctx: ExtensionCommandContext, repoRoot: string, opts: DraftLawOptions): Promise<void> {
	if (loopState.active) {
		fail(false, "draft-law: a loop is already running; settle or stop it before starting another.");
	}
	const { outAbs } = prepare(repoRoot, opts, false);
	const skillText = readFileSync(join(repoRoot, "pi", "skills", "drafting", "SKILL.md"), "utf8");
	const systemPrompt = `You draft Potato Hamlet law artefacts.\n\n${skillText}`;
	const asked = new Set<string>();
	const answersGiven: Record<string, string> = {};
	let reextractNote: string | undefined;

	try {
		for (;;) {
			const prompt = buildPassPrompt({
				rendered: Object.fromEntries(
					["ontology.ttl", "rules.lean", "manifest.yaml"].map((n) => [n, readFileSync(join(outAbs, "render", `${n}.prompt.md`), "utf8")]),
				),
				answers: answersGiven,
				skillRef: "the system prompt guidance above (the drafting skill is inlined; do not read it from disk)",
				reextractNote,
				maxPasses: opts.maxPasses,
			});
			noteSent();
			const passId = `pass-${loopState.passIndex}`;
			const promptWithId = `${prompt}\n\nCall report_ungroundable_steps with passId: "${passId}".`;
			const { toolCalls } = await nestedPass(ctx, systemPrompt, promptWithId);
			if (process.env.PI_DRAFT_LAW_DEBUG === "1") {
				console.error(`[draft-law debug pass ${loopState.passIndex}] tool calls: ${toolCalls.length}`);
			}

			let handoff: PassHandoff;
			const args = toolCalls[0]?.args as (ReportToolArgs | undefined);
			const argPassId = args?.passId;
			if (argPassId && isRedelivery(argPassId)) {
				if (process.env.PI_DRAFT_LAW_DEBUG === "1") {
					console.error(`[draft-law debug] duplicate receipt of passId ${argPassId} — redelivery ignored`);
				}
				consumePassId(argPassId);
				if (loopState.passIndex >= opts.maxPasses) {
					endLoop();
					fail(false, `draft-law: pass budget exhausted (${opts.maxPasses}) — draft is not complete`);
				}
				continue;
			}
			if (toolCalls.length === 0) {
				handoff = { drafts: {}, report: null, validity: null };
			} else {
				try {
					const outcome = executeReport(args!);
					handoff = { drafts: outcome.details.drafts, report: outcome.structuredContent, validity: [] };
				} catch (e) {
					handoff = { drafts: {}, report: { report: [] }, validity: [(e as Error).message] };
				}
			}
			const action = decide(handoff.report, handoff.validity, asked);
			const headlessPassId = (toolCalls[0]?.args as ReportToolArgs)?.passId;
			recordPass(handoff.report, handoff.validity, headlessPassId);
			writeOutputs(outAbs, handoff.drafts, handoff.report);

			if (action.kind === "converged") {
				const verdict = runHamletCheck(outAbs, { repoRoot }, opts.gateFull);
				endLoop();
				if (verdict.kind === "pass") return;
				const finding = verdict.kind === "refused" ? verdict.findings.join(" / ") : verdict.error;
				fail(false, `draft-law: converged but the gate refuses the draft: ${finding}`);
			}
			if (action.kind === "reextract") {
				reextractNote = action.reasons.join(" ");
				if (loopState.passIndex >= opts.maxPasses) {
					endLoop();
					fail(false, `draft-law: pass budget exhausted (${opts.maxPasses}) — draft is not complete`);
				}
				continue;
			}
			if (action.kind === "stalled") {
				endLoop();
				fail(false,
					`draft-law: no progress — every outstanding step was already asked and still came back ` +
						`ungrounded. Stopping rather than re-asking; drafts plus report written to ${outAbs}.`,
				);
			}
			// ask
			const noAnswer = action.steps.filter((s) => !(s.step in loopState.bank));
			if (process.env.PI_DRAFT_LAW_DEBUG === "1") {
				console.error(`[draft-law debug] asked so far: ${JSON.stringify([...loopState.asked, ...action.steps.map((s) => s.step)])}`);
			}
			if (noAnswer.length > 0) {
				endLoop();
				fail(false,
					`draft-law: questions outstanding (${noAnswer.length} unanswered, no UI to ask) — ` +
						`drafts plus report written to ${outAbs}. Draft is not complete.`,
				);
			}
			for (const step of action.steps) {
				answersGiven[step.step] = loopState.bank[step.step] as string;
				loopState.asked.push(step.step);
				asked.add(step.step);
			}
			reextractNote = undefined;
			if (loopState.passIndex >= opts.maxPasses) {
				endLoop();
				fail(false, `draft-law: pass budget exhausted (${opts.maxPasses}) — draft is not complete`);
			}
		}
	} finally {
		if (loopState.active) endLoop();
	}
}

/** The driver: consumes each settled pass while one is expected. */
async function driveSettledPass(pi: ExtensionAPI, ctx: { ui: ExtensionCommandContext["ui"]; hasUI: boolean; sessionManager: ExtensionCommandContext["sessionManager"] }): Promise<void> {
	if (!expectingPass() || loopState.busy) return;
	loopState.busy = true;
	try {
		await consumeSettledPass(pi, ctx);
	} catch (e) {
		// An unexpected failure inside the driver must still honor the
		// writes-and-exits contract: agent_end errors otherwise surface as
		// notices with a zero exit.
		const msg = `draft-law: driver failed: ${(e as Error).message}`;
		try {
			ctx.ui.notify(msg, "error");
		} catch {
			/* notify itself failed; the throw below still carries it */
		}
		endLoop();
		if (!ctx.hasUI) fail(false, msg);
	} finally {
		loopState.busy = false;
	}
}

/** One settled pass consumed: validate, ask or converge, trigger the next. */
async function consumeSettledPass(
	pi: ExtensionAPI,
	ctx: { ui: ExtensionCommandContext["ui"]; hasUI: boolean; sessionManager: ExtensionCommandContext["sessionManager"] },
): Promise<void> {
		const branch = ctx.sessionManager.getBranch();
		debugBranch(`consume pass ${loopState.passIndex}`, branch, loopState.branchStartLen);
		const handoff = scanHandoff(branch, loopState.branchStartLen);
		// Redelivery check: a pass bearing an already-consumed passId is a
		// duplicate receipt — it opens no second question round.
		if (handoff.passId && isRedelivery(handoff.passId)) {
			loopState.busy = false;
			ctx.ui.notify(`draft-law: duplicate receipt of passId ${handoff.passId} — redelivery ignored, no question round opened.`, "info");
			return;
		}
		const asked = new Set(loopState.asked);
		const action = decide(handoff.report, handoff.validity, asked);
		recordPass(handoff.report, handoff.validity, handoff.passId);
		writeOutputs(loopState.outDir, handoff.drafts, handoff.report);
		const outAbs = loopState.outDir;

		if (action.kind === "converged") {
			const verdict = runHamletCheck(outAbs, { repoRoot: loopState.repoRoot }, loopState.gateFull);
			if (verdict.kind === "pass") {
				endLoop();
				ctx.ui.notify(`draft-law: converged — gate passes over the world merge. Draft presented as complete.`, "info");
				return;
			}
			const finding = verdict.kind === "refused" ? verdict.findings.join(" / ") : verdict.error;
			endLoop();
			ctx.ui.notify(`draft-law: converged but the gate refuses the draft: ${finding}`, "error");
			if (!ctx.hasUI) fail(false, `draft-law: converged but the gate refuses the draft: ${finding}`);
			return;
		}

		if (action.kind === "reextract") {
			if (loopState.passIndex >= loopState.maxPasses) {
				endLoop();
				const msg = `draft-law: pass budget exhausted (${loopState.maxPasses}) — draft is not complete`;
				ctx.ui.notify(msg, "error");
				if (!ctx.hasUI) fail(false, msg);
				return;
			}
			sendPass(pi, ctx.sessionManager.getBranch().length, action.reasons.join(" "));
			return;
		}

		if (action.kind === "stalled") {
			endLoop();
			const msg =
				`draft-law: no progress — every outstanding step was already asked and still came back ` +
				`ungrounded. Stopping rather than re-asking; drafts plus report written to ${outAbs}.`;
			ctx.ui.notify(msg, "error");
			if (!ctx.hasUI) fail(false, msg);
			return;
		}

		// action.kind === "ask". Asked steps go to the author and into the
		// next pass as context only — never to disk.
		for (const step of action.steps) {
			ctx.ui.notify(`draft-law Q: ${step.step} — ${step["why-ungroundable"]}`, "info");
		}
		if (process.env.PI_DRAFT_LAW_DEBUG === "1") {
			console.error(`[draft-law debug] asked so far: ${JSON.stringify([...loopState.asked, ...action.steps.map((s) => s.step)])}`);
		}
		if (!ctx.hasUI) {
			// Headless: the answers file stands in for the author. A step
			// with no scripted answer stops the run; banked answers feed the
			// next pass exactly like interactive ones.
			const noAnswer = action.steps.filter((s) => !(s.step in loopState.bank));
			if (noAnswer.length > 0) {
				endLoop();
				fail(false,
					`draft-law: questions outstanding (${noAnswer.length} unanswered, no UI to ask) — ` +
						`drafts plus report written to ${outAbs}. Draft is not complete.`,
				);
			}
			for (const step of action.steps) {
				loopState.answersGiven[step.step] = loopState.bank[step.step] as string;
				loopState.asked.push(step.step);
			}
		} else {
			let stopped = false;
			for (const step of action.steps) {
				if (step.step in loopState.bank) {
					loopState.answersGiven[step.step] = loopState.bank[step.step] as string;
					loopState.asked.push(step.step);
					continue;
				}
				const answer = await ctx.ui.input(step.step, step["why-ungroundable"]);
				if (answer === undefined || answer.trim() === "") {
					stopped = true;
					break;
				}
				loopState.answersGiven[step.step] = answer;
				loopState.bank[step.step] = answer;
				loopState.asked.push(step.step);
			}
			if (stopped) {
				endLoop();
				ctx.ui.notify(`draft-law: questions outstanding — draft is not complete. Drafts plus report in ${outAbs}.`, "warning");
				return;
			}
		}
		if (loopState.passIndex >= loopState.maxPasses) {
			endLoop();
			const msg = `draft-law: pass budget exhausted (${loopState.maxPasses}) — draft is not complete`;
			ctx.ui.notify(msg, "error");
			if (!ctx.hasUI) fail(false, msg);
			return;
		}
		sendPass(pi, ctx.sessionManager.getBranch().length, undefined);
}

export function registerDraftLaw(pi: ExtensionAPI): void {
	pi.registerCommand("draft-law", {
		description: `Run the clarification loop for a law case: render, extract, validate the report, ` +
			`ask about ungroundable steps, and re-extract until the report is empty and the gate passes. ` +
			`Usage: /draft-law <case> [--answers file] [--out dir] [--max-passes n] [--gate-mode schema|full]`,
		handler: async (args, ctx) => {
			let opts: DraftLawOptions;
			try {
				opts = parseArgs(args ?? "");
			} catch (e) {
				const msg = (e as Error).message;
				ctx.ui.notify(msg, "error");
				if (!ctx.hasUI) fail(false, msg);
				return;
			}
			if (!opts.caseDir) {
				const msg = "draft-law: usage: /draft-law <case> [--answers file] [--out dir] [--max-passes n] [--gate-mode schema|full]";
				ctx.ui.notify(msg, "error");
				if (!ctx.hasUI) fail(false, msg);
				return;
			}
			// Headless runs (-p, no UI) execute the loop synchronously with
			// nested model calls: -p runs the input and exits, so anything
			// queued for the turn system would be abandoned.
			if (!ctx.hasUI) {
				try {
					await runHeadlessLoop(ctx, ctx.cwd, opts);
				} catch (e) {
					if (process.exitCode !== 1) {
						try {
							process.exitCode = 1;
						} catch {
							/* ignore */
						}
					}
					throw e;
				}
				return;
			}
			try {
				await kickoff(pi, ctx, ctx.cwd, opts);
			} catch (e) {
				// kickoff throws only via fail() (already counted) or on an
				// unexpected setup failure (render crash).
				throw e;
			}
		},
	});
	pi.on("agent_end", async (_event, ctx) => {
		await driveSettledPass(pi, ctx);
	});
}
