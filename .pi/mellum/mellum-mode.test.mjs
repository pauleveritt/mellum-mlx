import assert from "node:assert/strict";
import test from "node:test";
import { filterForMellum, MARK_ON, MARK_OFF, BOOTSTRAP_MARKER } from "./mellum-mode.ts";

const text = (role, t) => ({ role, content: [{ type: "text", text: t }] });

test("after the on-marker: system replaced, earlier history and the bootstrap dropped, reasoning kept", () => {
	const payload = {
		model: "x",
		messages: [
			{ role: "system", content: "pi base prompt + skills catalog" },
			text("user", `${BOOTSTRAP_MARKER} ... superpowers`),
			text("user", "parent task"),
			{ role: "assistant", content: "parent answer", reasoning_content: "parent thoughts" },
			text("user", MARK_ON),
			text("user", "fix the cart total"),
			{ role: "assistant", content: "", reasoning_content: "mine", tool_calls: [{ id: "1" }] },
			{ role: "tool", tool_call_id: "1", content: "r" },
		],
	};
	const out = filterForMellum(payload, "v5 prompt");
	assert.equal(out.messages[0].role, "system");
	assert.equal(out.messages[0].content, "v5 prompt");
	assert.deepEqual(out.messages.slice(1).map(m => m.role), ["user", "assistant", "tool"]);
	assert.equal(out.messages[1].content[0].text, "fix the cart total");
	assert.equal(out.messages[2].reasoning_content, "mine", "own thinking stays (A12)");
	assert.equal(payload.messages.length, 8, "input not mutated");
});

test("without an on-marker (headless activation) only the bootstrap is dropped", () => {
	const payload = { messages: [{ role: "system", content: "base" }, text("user", `${BOOTSTRAP_MARKER} x`), text("user", "task")] };
	const out = filterForMellum(payload, "v5");
	assert.deepEqual(out.messages.map(m => m.role), ["system", "user"]);
	assert.equal(out.messages[1].content[0].text, "task");
});

test("a prompt queued just before the on-marker is kept, and marker messages never reach the model", () => {
	const payload = {
		messages: [
			{ role: "system", content: "base" },
			text("user", "fix the cart total"),
			text("user", MARK_ON),
		],
		tools: [{ type: "function", function: { name: "read" } }, { type: "function", function: { name: "subagent" } }],
	};
	const out = filterForMellum(payload, "v5");
	assert.deepEqual(out.messages.map(m => m.role), ["system", "user"]);
	assert.equal(out.messages[1].content[0].text, "fix the cart total");
	assert.ok(!JSON.stringify(out.messages).includes(MARK_ON));
	assert.deepEqual(out.tools.map(t => t.function.name), ["read"], "pi-subagents' re-added tools are filtered out");
});

test("a developer-role instruction message is replaced too, and tool_choice naming a removed tool is dropped", () => {
	const payload = {
		messages: [{ role: "developer", content: "pi base" }, text("user", "task")],
		tools: [{ type: "function", function: { name: "subagent" } }],
		tool_choice: { type: "function", function: { name: "subagent" } },
	};
	const out = filterForMellum(payload, "v5");
	assert.deepEqual(out.messages.map(m => m.role), ["system", "user"]);
	assert.ok(!("tools" in out), "an empty tool list is removed, not sent");
	assert.ok(!("tool_choice" in out));
});

test("markers between the prompt and the on-marker are skipped: [prompt, OFF, ON] keeps the prompt", () => {
	const payload = { messages: [{ role: "system", content: "base" }, text("user", "task"), text("user", MARK_OFF), text("user", MARK_ON)] };
	const out = filterForMellum(payload, "v5");
	assert.deepEqual(out.messages.map(m => m.role), ["system", "user"]);
	assert.equal(out.messages[1].content[0].text, "task");
});

test("a missing marker while interactively active is reported, not silently widened", () => {
	const payload = { messages: [{ role: "system", content: "base" }, text("user", "old parent turn"), text("user", "task")] };
	const out = filterForMellum(payload, "v5", { expectMarker: true });
	assert.equal(out.messages.length, 2, "only the system prompt and the last user message survive");
	assert.equal(out.messages[1].content[0].text, "task");
	assert.equal(out.mellumModeMarkerMissing, true);
});

test("after /mellum off, the parent sees one handoff block in place of the mode's turns", async () => {
	const { collapseHandoffs, MARK_OFF } = await import("./mellum-mode.ts");
	const msgs = [
		text("user", "earlier parent turn"),
		{ role: "assistant", content: [{ type: "text", text: "parent reply" }] },
		text("user", "fix the cart total"),
		text("user", MARK_ON),
		{ role: "assistant", content: [{ type: "thinking", thinking: "..." }, { type: "toolCall", id: "1", name: "read", arguments: { path: "calculator.js" } }] },
		{ role: "toolResult", toolCallId: "1", toolName: "read", content: [{ type: "text", text: "export function total() {}" }] },
		{ role: "assistant", content: [{ type: "toolCall", id: "2", name: "edit", arguments: { path: "calculator.js", edits: [] } }] },
		{ role: "toolResult", toolCallId: "2", toolName: "edit", content: [{ type: "text", text: "Successfully replaced 1 block(s)" }] },
		{ role: "assistant", content: [{ type: "toolCall", id: "3", name: "bash", arguments: { command: "node --test calculator.test.js" } }] },
		{ role: "toolResult", toolCallId: "3", toolName: "bash", content: [{ type: "text", text: "ℹ pass 3\nℹ fail 0" }] },
		{ role: "assistant", content: [{ type: "text", text: "Files changed: calculator.js. Tests pass." }] },
		text("user", MARK_OFF),
		text("user", "thanks, now the docs"),
	];
	const out = collapseHandoffs(msgs);
	assert.deepEqual(out.map(m => m.role), ["user", "assistant", "user", "user"]);
	const handoff = out[2].content[0].text;
	assert.match(handoff, /\[mellum-mode handoff\]/);
	assert.match(handoff, /fix the cart total/);
	assert.match(handoff, /calculator\.js/);
	assert.match(handoff, /pass 3/);
	assert.match(handoff, /Tests pass\./);
	assert.ok(!handoff.includes("export function total"), "tool results are summarised, not replayed");
	assert.equal(out[3].content[0].text, "thanks, now the docs");
	assert.equal(msgs.length, 13, "input not mutated");
});

test("an open span (mode still on) is left alone by the collapse", async () => {
	const { collapseHandoffs } = await import("./mellum-mode.ts");
	const msgs = [text("user", "task"), text("user", MARK_ON), { role: "assistant", content: [{ type: "text", text: "working" }] }];
	assert.deepEqual(collapseHandoffs(msgs), msgs);
});

test("a new prompt queued before the off-marker is kept after the handoff", async () => {
	const { collapseHandoffs, MARK_OFF } = await import("./mellum-mode.ts");
	const msgs = [
		text("user", "fix it"),
		text("user", MARK_ON),
		{ role: "assistant", content: [{ type: "text", text: "done" }] },
		text("user", "now the docs"),
		text("user", MARK_OFF),
	];
	const out = collapseHandoffs(msgs);
	assert.deepEqual(out.map(m => m.role), ["user", "user"]);
	assert.match(out[0].content[0].text, /handoff/);
	assert.equal(out[1].content[0].text, "now the docs");
});

test("markers arrive at the context event as custom messages, not user messages", async () => {
	const { collapseHandoffs, MARK_OFF } = await import("./mellum-mode.ts");
	const custom = (t) => ({ role: "custom", customType: "mellum-mode", content: [{ type: "text", text: t }] });
	const msgs = [
		text("user", "fix it"),
		custom(MARK_ON),
		{ role: "assistant", content: [{ type: "text", text: "done" }] },
		text("user", "now the docs"),
		custom(MARK_OFF),
	];
	const out = collapseHandoffs(msgs);
	assert.deepEqual(out.map(m => m.role), ["user", "user"]);
	assert.match(out[0].content[0].text, /handoff/);
});
