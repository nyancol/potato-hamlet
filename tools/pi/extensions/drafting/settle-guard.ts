/**
 * agent_before_settle backstop: refuses to settle while a completed loop pass
 * is unconverged and no follow-up was sent. Backstop, not driver — it fires
 * only when the run reaches the settle boundary outside the driver's own
 * flow (e.g. a conversational detour presenting a draft as complete).
 *
 * A driver-sent follow-up (sentSeq past doneSeq) means the loop is
 * progressing, so the guard stands down instead of nagging mid-flight.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { loopState } from "./loop-state.ts";

const GUARD_TYPE = "draft-law-guard";

export function settleProblems(): string[] {
	if (!loopState.active) return [];
	// No completed pass, or a follow-up already sent: nothing to guard.
	if (loopState.doneSeq < 0 || loopState.sentSeq !== loopState.doneSeq) return [];
	const problems: string[] = [];
	if (loopState.lastReport === null || loopState.lastValidity === null) {
		problems.push("a /draft-law pass completed with no validated report on record");
		return problems;
	}
	if (loopState.lastValidity.length > 0) {
		problems.push(`the last report is invalid: ${loopState.lastValidity[0]}`);
	}
	if (loopState.lastReport.report.length > 0) {
		const steps = loopState.lastReport.report.map((e) => JSON.stringify(e.step)).join("; ");
		problems.push(`${loopState.lastReport.report.length} step(s) still ungrounded: ${steps}`);
	}
	const seen = new Set<string>();
	for (const step of loopState.asked) {
		if (seen.has(step)) problems.push(`step asked twice: ${JSON.stringify(step)}`);
		seen.add(step);
	}
	return problems;
}

export function registerSettleGuard(pi: ExtensionAPI): void {
	pi.on("agent_before_settle", async (_event, _ctx) => {
		const problems = settleProblems();
		if (problems.length === 0) return {};
		return {
			entries: [
				{
					type: "custom_message",
					customType: GUARD_TYPE,
					content:
						`Draft presented as complete while the clarification loop is unconverged — ` +
						`do not settle. ${problems.join(" ")} Re-extract via report_ungroundable_steps ` +
						`or keep asking; an empty validated report plus a passing gate is the only exit.`,
					display: true,
				},
			],
			continue: true,
		};
	});
}
