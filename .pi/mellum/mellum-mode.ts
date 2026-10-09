/**
 * Mellum mode: run the small model inside the main session with the worker's prompt
 * and tools, and show it nothing from before the mode began.
 *
 *   /mellum <task>  – one shot: switch to Mellum, run the task, switch back when settled
 *   /mellum on      – stay on for several turns (switch model, tools, mark the start)
 *   /mellum off     – restore the previous model and tools
 *
 * While on, before_provider_request rewrites the outgoing payload: the system message
 * becomes the worker prompt (prompts/mellum-worker.md, or $MELLUM_MODE_PROMPT), and the
 * messages are only those after the on-marker, minus Superpowers' bootstrap message.
 * Earlier turns' reasoning_content is left in place: removing it made runs 60% slower
 * (ladder A12). The session keeps everything, so the parent sees the mode's work after
 * /mellum off.
 *
 * Headless: MELLUM_MODE=1 activates at session start (the ladder's "mode" runner).
 * Load alongside mellum-guards.ts; this file does not auto-load (it is not in .pi/extensions/).
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const MARK_ON = "[mellum-mode on]";
export const MARK_OFF = "[mellum-mode off]";
export const BOOTSTRAP_MARKER = "superpowers:using-superpowers bootstrap for pi";
export const WORKER_TOOLS = ["read", "grep", "find", "ls", "bash", "edit", "write"];
const DEFAULT_MODEL = { provider: "omlx", id: "Mellum2.1-12B-A2.5B-Thinking-6bit" };

type Msg = { role?: string; content?: unknown; [k: string]: unknown };

function textOf(m: Msg): string {
	if (typeof m.content === "string") return m.content;
	if (!Array.isArray(m.content)) return "";
	return m.content.map((p: any) => (p && p.type === "text" && typeof p.text === "string" ? p.text : "")).join("\n");
}

const INSTRUCTION_ROLES = new Set(["system", "developer"]);

export function filterForMellum(payload: any, systemPrompt: string, opts: { expectMarker?: boolean } = {}) {
	if (!payload || !Array.isArray(payload.messages)) return payload;
	const msgs: Msg[] = payload.messages;
	const isMarker = (m: Msg) => m.role === "user" && (textOf(m).includes(MARK_ON) || textOf(m).includes(MARK_OFF));
	const isBootstrap = (m: Msg) => textOf(m).includes(BOOTSTRAP_MARKER);
	let start = 0;
	let markerAt = -1;
	for (let i = msgs.length - 1; i >= 0; i--) {
		if (msgs[i].role === "user" && textOf(msgs[i]).includes(MARK_ON)) {
			markerAt = i;
			break;
		}
	}
	let markerMissing = false;
	if (markerAt >= 0) {
		start = markerAt + 1;
		// Pi delivers a queued marker after the user message it was queued for, so the
		// prompt that started the mode sits just before the marker (possibly behind an
		// off-marker). Keep it unless a later user message already carries the task.
		const laterUser = msgs.slice(start).some((m) => m.role === "user" && !isMarker(m));
		if (!laterUser) {
			let j = markerAt - 1;
			while (j >= 0 && isMarker(msgs[j])) j--;
			if (j >= 0 && msgs[j].role === "user" && !isBootstrap(msgs[j])) start = j;
		}
	} else if (opts.expectMarker) {
		// The marker was compacted away or never arrived: send only the last user
		// message rather than the whole parent history, and say so.
		markerMissing = true;
		for (let i = msgs.length - 1; i >= 0; i--) {
			if (msgs[i].role === "user" && !isMarker(msgs[i]) && !isBootstrap(msgs[i])) {
				start = i;
				break;
			}
		}
	}
	const kept = msgs
		.slice(start)
		.filter((m) => !INSTRUCTION_ROLES.has(m.role ?? "") && !isMarker(m) && !isBootstrap(m));
	const out: any = { ...payload, messages: [{ role: "system", content: systemPrompt }, ...kept] };
	if (Array.isArray(payload.tools)) {
		// pi-subagents re-adds its own tools after setActiveTools; the worker gets only its seven.
		const tools = payload.tools.filter((t: any) => WORKER_TOOLS.includes(t?.function?.name ?? t?.name));
		if (tools.length) out.tools = tools;
		else delete out.tools;
		const chosen = payload.tool_choice?.function?.name ?? payload.tool_choice?.name;
		if (chosen && !WORKER_TOOLS.includes(chosen)) delete out.tool_choice;
	}
	if (markerMissing) out.mellumModeMarkerMissing = true;
	return out;
}

function loadPrompt(): string {
	const here = dirname(fileURLToPath(import.meta.url));
	const file = process.env.MELLUM_MODE_PROMPT || resolve(here, "..", "..", "prompts", "mellum-worker.md");
	return readFileSync(file, "utf8").trim();
}

export default function (pi: any) {
	let active = false;
	let interactive = false;
	let saved: { model: any; tools: string[] } | undefined;
	let prompt = "";
	let warnedMissing = false;

	async function activate(ctx: any, notify = true) {
		if (active) {
			ctx.ui?.notify?.("mellum-mode is already on", "info");
			return;
		}
		const provider = process.env.MELLUM_MODE_PROVIDER || DEFAULT_MODEL.provider;
		const id = process.env.MELLUM_MODE_MODEL || DEFAULT_MODEL.id;
		const model = ctx.modelRegistry.find(provider, id);
		if (!model) {
			ctx.ui?.notify?.(`mellum-mode: model ${provider}/${id} not found; mode stays off`, "error");
			return;
		}
		const previous = { model: ctx.model, tools: pi.getActiveTools() };
		prompt = loadPrompt();
		const switched = await pi.setModel(model);
		if (!switched) {
			ctx.ui?.notify?.(`mellum-mode: could not select ${provider}/${id} (auth or provider error); mode stays off`, "error");
			return;
		}
		saved = previous;
		pi.setActiveTools(WORKER_TOOLS);
		active = true;
		interactive = notify;
		warnedMissing = false;
		if (notify) pi.sendMessage({ customType: "mellum-mode", content: MARK_ON, display: true }, { deliverAs: "nextTurn" });
		if (notify) ctx.ui?.notify?.(`mellum-mode on: ${provider}/${id}, tools ${WORKER_TOOLS.join(",")}`, "info");
	}

	async function deactivate(ctx: any) {
		if (!active) {
			ctx.ui?.notify?.("mellum-mode is not on", "info");
			return;
		}
		if (!saved?.model) {
			ctx.ui?.notify?.("mellum-mode: no previous model to restore; staying on. Pick a model with /model, then /mellum off.", "warning");
			return;
		}
		const restored = await pi.setModel(saved.model);
		if (!restored) {
			ctx.ui?.notify?.("mellum-mode: could not restore the previous model; staying on", "error");
			return;
		}
		pi.setActiveTools(saved.tools);
		active = false;
		pi.sendMessage({ customType: "mellum-mode", content: MARK_OFF, display: true }, { deliverAs: "nextTurn" });
		ctx.ui?.notify?.("mellum-mode off", "info");
	}

	let oneShot = false;

	pi.registerCommand("mellum", {
		description: "mellum <task> | on | off — run Mellum with the worker prompt and tools inside this session",
		handler: async (args: string, ctx: any) => {
			const want = (args || "").trim();
			if (want === "off") return deactivate(ctx);
			if (want === "on" || want === "") return activate(ctx);
			// One shot: the task runs under the mode and the mode ends when the agent settles.
			if (active) {
				ctx.ui?.notify?.("mellum-mode is already on; type the task as a normal prompt, or /mellum off first", "warning");
				return;
			}
			await activate(ctx);
			if (!active) return;
			oneShot = true;
			pi.sendUserMessage(want);
		},
	});

	pi.on("agent_settled", async (_event: any, ctx: any) => {
		if (active && oneShot) {
			oneShot = false;
			await deactivate(ctx);
		}
	});

	pi.on("session_start", async (_event: any, ctx: any) => {
		if (process.env.MELLUM_MODE === "1" && !active) await activate(ctx, false);
	});

	// Pi sizes auto-compaction against the active model's window (Mellum's 56k) over the
	// whole, unfiltered session. Compacting the parent's history with Mellum would be a
	// lossy change to the user's session, and it would erase the on-marker. Refuse while on.
	pi.on("session_before_compact", (event: any, ctx: any) => {
		if (!active || event?.reason === "manual") return undefined;
		ctx.ui?.notify?.("mellum-mode: auto-compaction skipped while the mode is on (/mellum off first, or /compact)", "warning");
		return { cancel: true };
	});

	pi.on("before_provider_request", (event: any, ctx: any) => {
		if (!active) return undefined;
		const out = filterForMellum(event.payload, prompt, { expectMarker: interactive });
		if (out?.mellumModeMarkerMissing) {
			delete out.mellumModeMarkerMissing;
			if (!warnedMissing) {
				warnedMissing = true;
				ctx?.ui?.notify?.("mellum-mode: the on-marker is gone from the context; sending only the last message", "warning");
			}
		}
		return out;
	});
}
