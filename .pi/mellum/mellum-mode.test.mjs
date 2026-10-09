import assert from "node:assert/strict";
import test from "node:test";
import { filterForMellum, MARK_ON, BOOTSTRAP_MARKER } from "./mellum-mode.ts";

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
