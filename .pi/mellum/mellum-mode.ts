/**
 * Mellum mode: run the small model inside the main session with the worker's prompt
 * and tools, and show it nothing from before the mode began.
 *
 *   /mellum on   – switch model to Mellum, tools to the worker's seven, mark the start
 *   /mellum off  – restore the previous model and tools
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

export function filterForMellum(payload: any, systemPrompt: string) {
	if (!payload || !Array.isArray(payload.messages)) return payload;
	const msgs: Msg[] = payload.messages;
	let start = 0;
	for (let i = msgs.length - 1; i >= 0; i--) {
		if (msgs[i].role === "user" && textOf(msgs[i]).includes(MARK_ON)) {
			start = i + 1;
			break;
		}
	}
	const kept = msgs.slice(start).filter((m) => !(m.role === "system") && !textOf(m).includes(BOOTSTRAP_MARKER));
	return { ...payload, messages: [{ role: "system", content: systemPrompt }, ...kept] };
}

function loadPrompt(): string {
	const here = dirname(fileURLToPath(import.meta.url));
	const file = process.env.MELLUM_MODE_PROMPT || resolve(here, "..", "..", "prompts", "mellum-worker.md");
	return readFileSync(file, "utf8").trim();
}

export default function (pi: any) {
	let active = false;
	let saved: { model: any; tools: string[] } | undefined;
	let prompt = "";

	async function activate(ctx: any, notify = true) {
		const provider = process.env.MELLUM_MODE_PROVIDER || DEFAULT_MODEL.provider;
		const id = process.env.MELLUM_MODE_MODEL || DEFAULT_MODEL.id;
		const model = ctx.modelRegistry.find(provider, id);
		if (!model) {
			ctx.ui?.notify?.(`mellum-mode: model ${provider}/${id} not found`, "error");
			return;
		}
		saved = { model: ctx.model, tools: pi.getActiveTools() };
		prompt = loadPrompt();
		await pi.setModel(model);
		pi.setActiveTools(WORKER_TOOLS);
		active = true;
		pi.sendMessage({ customType: "mellum-mode", content: MARK_ON, display: true }, { deliverAs: "nextTurn" });
		if (notify) ctx.ui?.notify?.(`mellum-mode on: ${provider}/${id}, tools ${WORKER_TOOLS.join(",")}`, "info");
	}

	async function deactivate(ctx: any) {
		active = false;
		if (saved) {
			if (saved.model) await pi.setModel(saved.model);
			pi.setActiveTools(saved.tools);
		}
		pi.sendMessage({ customType: "mellum-mode", content: MARK_OFF, display: true }, { deliverAs: "nextTurn" });
		ctx.ui?.notify?.("mellum-mode off", "info");
	}

	pi.registerCommand("mellum", {
		description: "mellum on|off — run Mellum with the worker prompt and tools inside this session",
		handler: async (args: string, ctx: any) => {
			const want = (args || "").trim();
			if (want === "off") return deactivate(ctx);
			if (want === "on" || want === "") return activate(ctx);
			ctx.ui?.notify?.("usage: /mellum on|off", "warning");
		},
	});

	pi.on("session_start", async (_event: any, ctx: any) => {
		if (process.env.MELLUM_MODE === "1" && !active) await activate(ctx, false);
	});

	pi.on("before_provider_request", (event: any) => {
		if (!active) return undefined;
		return filterForMellum(event.payload, prompt);
	});
}
