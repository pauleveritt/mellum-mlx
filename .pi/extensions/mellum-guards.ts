/**
 * Child-only guards for the Mellum worker: pure `ToolCall -> Decision`
 * functions in the shape proven in ../local-ai-pi/extensions/guards, adapted
 * to Pi's `tool_call` hook at the bottom of this file.
 *
 * Each guard exists for a recorded pathology:
 * - newFileOnlyWrite: a model wrote the changed fragment as the whole file
 *   (942 lines -> 2) under a write-only envelope. The refusal states the fact
 *   the model lacked, at the moment it matters.
 * - createLoopBreaker: 245 identical `ls -R` calls, all successful; ported
 *   unchanged (window 20, threshold 5, keyed on tool + sorted arguments).
 * - createStepBudget: Pi has no turn cap; a budget that blocks with a reason
 *   to summarise beats an abort, which the parent reads as a failed run.
 * - createEmptyFinalNudge: the one pathology the ladder recorded (5 of 45
 *   v3 runs, every failure): a turn ends with `stop`, no text, no tool call,
 *   part-way through the task. At `agent_before_settle` the guard proposes
 *   one custom message restating the completion fact and asks for one more
 *   model request, at most `max` times per run.
 *
 * ENABLED is set from the phase 0-1 ladder tables: a guard is on only for a
 * column that was non-zero. Empty means every guard is dormant.
 */

import { existsSync } from "node:fs";
import { isAbsolute, resolve } from "node:path";

export interface ToolCall {
	toolName: string;
	input: unknown;
}

export interface Block {
	block: true;
	reason: string;
}

export type Decision = Block | undefined;
export type Guard = (call: ToolCall) => Decision;

export const ENABLED: {
	newFileOnlyWrite?: boolean;
	loopBreaker?: boolean;
	stepBudget?: number;
	emptyFinalNudge?: number;
} = { emptyFinalNudge: 1 };

export const NUDGE_TEXT =
	"[mellum-guard] Your last turn ended with no reply and no tool call. " +
	"The task is complete only when the test command exits 0. " +
	"Continue: run the next step, and when the tests pass reply with the files changed and the test output.";

interface MessageLike {
	role?: string;
	content?: unknown;
}

export interface Continuation {
	entries: { type: "custom_message"; customType: string; content: string; display: boolean }[];
	continue: true;
}

function isEmptyAssistantTurn(message: MessageLike): boolean {
	if (message.role !== "assistant") return false;
	const blocks = Array.isArray(message.content) ? (message.content as Record<string, unknown>[]) : [];
	const hasText = blocks.some((b) => b.type === "text" && typeof b.text === "string" && b.text.trim() !== "");
	const hasCall = blocks.some((b) => b.type === "toolCall");
	return !hasText && !hasCall;
}

export function createEmptyFinalNudge(max: number): (message: MessageLike) => Continuation | undefined {
	let used = 0;
	return (message) => {
		if (!isEmptyAssistantTurn(message) || used >= max) return undefined;
		used += 1;
		return {
			entries: [{ type: "custom_message", customType: "mellum-guard", content: NUDGE_TEXT, display: true }],
			continue: true,
		};
	};
}

export function callKey(toolName: string, input: unknown): string {
	const stable = (value: unknown): unknown => {
		if (Array.isArray(value)) return value.map(stable);
		if (value && typeof value === "object") {
			return Object.fromEntries(
				Object.entries(value as Record<string, unknown>)
					.sort(([a], [b]) => a.localeCompare(b))
					.map(([k, v]) => [k, stable(v)]),
			);
		}
		return value;
	};
	return `${toolName}\u0000${JSON.stringify(stable(input))}`;
}

function pathOf(input: unknown): string | undefined {
	if (!input || typeof input !== "object") return undefined;
	const record = input as Record<string, unknown>;
	for (const key of ["path", "filePath", "file_path"]) {
		if (typeof record[key] === "string") return record[key] as string;
	}
	return undefined;
}

export const newFileOnlyWrite =
	(exists: (path: string) => boolean): Guard =>
	(call) => {
		if (call.toolName !== "write") return undefined;
		const path = pathOf(call.input);
		if (!path || !exists(path)) return undefined;
		return {
			block: true,
			reason:
				`${path} exists; write replaces the entire file. ` +
				`Use edit for an existing file: give the exact old text and the new text.`,
		};
	};

export function createLoopBreaker(window = 20, threshold = 5): Guard {
	const recent: string[] = [];
	return (call) => {
		const key = callKey(call.toolName, call.input);
		const seen = recent.filter((entry) => entry === key).length;
		if (seen >= threshold) {
			return {
				block: true,
				reason:
					`You have already run this exact ${call.toolName} call ${seen} times ` +
					`in a row and the result will not change. Do not repeat it. ` +
					`Use what you already know and take the next concrete action.`,
			};
		}
		recent.push(key);
		if (recent.length > window) recent.shift();
		return undefined;
	};
}

export function createStepBudget(max: number): Guard {
	let calls = 0;
	return () => {
		calls += 1;
		if (calls <= max) return undefined;
		return {
			block: true,
			reason: `Tool-call budget of ${max} reached. Summarise what was done and what remains, then stop.`,
		};
	};
}

/** The MELLUM_GUARDS environment variable (JSON) replaces ENABLED, for live smokes such as {"stepBudget":1}. */
export function resolveEnabled(defaults: typeof ENABLED, env: string | undefined): typeof ENABLED {
	if (!env) return defaults;
	try {
		const parsed = JSON.parse(env);
		return parsed && typeof parsed === "object" ? parsed : defaults;
	} catch {
		return defaults;
	}
}

export function activeGuards(enabled = ENABLED, cwd = process.cwd()): Guard[] {
	const guards: Guard[] = [];
	if (enabled.newFileOnlyWrite) {
		guards.push(newFileOnlyWrite((p) => existsSync(isAbsolute(p) ? p : resolve(cwd, p))));
	}
	if (enabled.loopBreaker) guards.push(createLoopBreaker());
	if (enabled.stepBudget) guards.push(createStepBudget(enabled.stepBudget));
	return guards;
}

export default function (pi: { on: (event: string, handler: (event: any) => unknown) => void }) {
	const enabled = resolveEnabled(ENABLED, process.env.MELLUM_GUARDS);
	const guards = activeGuards(enabled);
	pi.on("tool_call", (event) => {
		for (const guard of guards) {
			const decision = guard({ toolName: event.toolName, input: event.input });
			if (decision?.block) return decision;
		}
		return undefined;
	});
	if (enabled.emptyFinalNudge) {
		// Pi reports canContinue=false on the final turn, which is exactly where an
		// empty final lands; agent_before_settle still honours continue:true there
		// (probed 2026-10-08 in print mode). Remember the last assistant turn, decide
		// at settle.
		const nudge = createEmptyFinalNudge(enabled.emptyFinalNudge);
		let lastAssistant: MessageLike | undefined;
		pi.on("turn_end", (event) => {
			if (event?.message?.role === "assistant") lastAssistant = event.message;
			return undefined;
		});
		pi.on("agent_before_settle", () => {
			if (!lastAssistant) return undefined;
			const decision = nudge(lastAssistant);
			if (decision) lastAssistant = undefined;
			return decision;
		});
	}
}
