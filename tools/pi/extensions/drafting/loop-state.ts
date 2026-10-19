/**
 * Loop state shared between the /draft-law command (kickoff), the agent_end
 * driver (consumer), and the settle guard (reader). One run at a time.
 *
 * Sequencing: every sent pass bumps sentSeq; the agent_end driver consumes
 * the current pass into doneSeq. The guard blocks settling only when a
 * completed pass is unconverged AND no follow-up was sent (sentSeq equals
 * doneSeq) — a driver-sent follow-up means the loop is progressing, so the
 * guard stands down instead of nagging mid-flight.
 */
import type { ClarificationReport } from "./loop-lib.ts";

export interface LoopSnapshot {
	active: boolean;
	busy: boolean;
	repoRoot: string;
	caseDir: string;
	outDir: string;
	bank: Record<string, string>;
	answersGiven: Record<string, string>;
	asked: string[];
	passIndex: number;
	maxPasses: number;
	gateFull: boolean;
	branchStartLen: number;
	sentSeq: number;
	doneSeq: number;
	/** The last consumed passId, for idempotent receipt detection. */
	lastPassId: string | null;
	/** Set of passIds already consumed this run. A re-delivery asks nothing. */
	consumedPassIds: Set<string>;
	lastReport: ClarificationReport | null;
	/** validateReport() output for the last pass, or null when no structured report arrived. */
	lastValidity: string[] | null;
}

export const loopState: LoopSnapshot = {
	active: false,
	busy: false,
	repoRoot: "",
	caseDir: "",
	outDir: "",
	bank: {},
	answersGiven: {},
	asked: [],
	passIndex: 0,
	maxPasses: 5,
	gateFull: false,
	branchStartLen: 0,
	sentSeq: -1,
	doneSeq: -1,
	lastPassId: null,
	consumedPassIds: new Set(),
	lastReport: null,
	lastValidity: null,
};

/**
 * True when a pass bearing `passId` was already consumed this run.
 * A redelivered passId must not open a second question round.
 */
export function isRedelivery(passId: string | undefined | null): boolean {
	if (!passId) return false;
	return loopState.consumedPassIds.has(passId);
}

/** Record the consumed passId so a re-delivery is detected. */
export function consumePassId(passId: string | undefined | null): void {
	loopState.lastPassId = passId ?? null;
	if (passId) loopState.consumedPassIds.add(passId);
}

export function expectingPass(): boolean {
	return loopState.active && loopState.sentSeq > loopState.doneSeq;
}

export function resetLoop(opts: {
	repoRoot: string;
	caseDir: string;
	outDir: string;
	bank: Record<string, string>;
	maxPasses: number;
	gateFull: boolean;
}): void {
	loopState.active = true;
	loopState.busy = false;
	loopState.repoRoot = opts.repoRoot;
	loopState.caseDir = opts.caseDir;
	loopState.outDir = opts.outDir;
	loopState.bank = { ...opts.bank };
	loopState.answersGiven = {};
	loopState.asked = [];
	loopState.passIndex = 0;
	loopState.maxPasses = opts.maxPasses;
	loopState.gateFull = opts.gateFull;
	loopState.branchStartLen = 0;
	loopState.sentSeq = -1;
	loopState.doneSeq = -1;
	loopState.lastPassId = null;
	loopState.consumedPassIds = new Set();
	loopState.lastReport = null;
	loopState.lastValidity = null;
}

export function recordPass(report: ClarificationReport | null, validity: string[] | null, passId?: string | null): void {
	loopState.lastReport = report;
	loopState.lastValidity = validity;
	loopState.doneSeq = loopState.sentSeq;
	consumePassId(passId);
}

/** Stamp a sent pass (sequence + count). The command calls this per send. */
export function noteSent(): void {
	loopState.sentSeq += 1;
	loopState.passIndex += 1;
}

export function endLoop(): void {
	loopState.active = false;
	loopState.busy = false;
	loopState.repoRoot = "";
	loopState.caseDir = "";
	loopState.outDir = "";
	loopState.bank = {};
	loopState.answersGiven = {};
	loopState.asked = [];
	loopState.passIndex = 0;
	loopState.branchStartLen = 0;
	loopState.sentSeq = -1;
	loopState.doneSeq = -1;
	loopState.lastPassId = null;
	loopState.consumedPassIds = new Set();
	loopState.lastReport = null;
	loopState.lastValidity = null;
}
