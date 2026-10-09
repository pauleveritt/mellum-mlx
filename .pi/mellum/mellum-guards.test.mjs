import assert from "node:assert/strict";
import test from "node:test";

import { createLoopBreaker, createStepBudget, newFileOnlyWrite } from "./mellum-guards.ts";

test("write to an existing path is blocked with the fact", () => {
	const guard = newFileOnlyWrite((p) => p === "a.py");
	assert.equal(guard({ toolName: "write", input: { path: "b.py" } }), undefined);
	const decision = guard({ toolName: "write", input: { path: "a.py" } });
	assert.ok(decision.block);
	assert.match(decision.reason, /replaces the entire file/);
});

test("loop breaker trips on the sixth identical call, success or not", () => {
	const guard = createLoopBreaker(20, 5);
	const call = { toolName: "read", input: { path: "x" } };
	for (let i = 0; i < 5; i++) assert.equal(guard(call), undefined);
	assert.ok(guard(call).block);
});

test("loop breaker ignores differing calls", () => {
	const guard = createLoopBreaker(20, 5);
	for (let i = 0; i < 10; i++) assert.equal(guard({ toolName: "read", input: { path: `f${i}` } }), undefined);
});

test("step budget blocks after N calls", () => {
	const guard = createStepBudget(2);
	const call = { toolName: "ls", input: {} };
	assert.equal(guard(call), undefined);
	assert.equal(guard(call), undefined);
	assert.ok(guard(call).block);
});

test("empty-final nudge fires only on an assistant turn with no text and no tool call, up to the cap", async () => {
	const { createEmptyFinalNudge } = await import("./mellum-guards.ts");
	const nudge = createEmptyFinalNudge(2);
	const empty = { role: "assistant", content: [{ type: "thinking", thinking: "..." }] };
	const withText = { role: "assistant", content: [{ type: "text", text: "Done." }] };
	const withCall = { role: "assistant", content: [{ type: "toolCall", name: "read" }] };
	assert.equal(nudge(withText), undefined);
	assert.equal(nudge(withCall), undefined);
	assert.equal(nudge({ role: "user", content: "hi" }), undefined);
	const first = nudge(empty);
	assert.ok(first.continue);
	assert.equal(first.entries[0].type, "custom_message");
	assert.match(first.entries[0].content, /exits 0/);
	assert.ok(nudge(empty).continue);
	assert.equal(nudge(empty), undefined);
});

test("MELLUM_GUARDS env overrides ENABLED for live smokes", async () => {
	const { resolveEnabled } = await import("./mellum-guards.ts");
	assert.deepEqual(resolveEnabled({ emptyFinalNudge: 2 }, '{"stepBudget":1}'), { stepBudget: 1 });
	assert.deepEqual(resolveEnabled({ emptyFinalNudge: 2 }, undefined), { emptyFinalNudge: 2 });
	assert.deepEqual(resolveEnabled({ emptyFinalNudge: 2 }, "not json"), { emptyFinalNudge: 2 });
});

test("adapter nudges from agent_before_settle when the last assistant turn was empty", async () => {
	const { default: install } = await import("./mellum-guards.ts");
	const handlers = {};
	install({ on: (name, fn) => { handlers[name] = fn; } });
	const empty = { role: "assistant", content: [{ type: "thinking", thinking: "..." }, { type: "text", text: "\n\n" }] };
	const done = { role: "assistant", content: [{ type: "text", text: "Done." }] };
	handlers.turn_end({ message: empty, context: { canContinue: false }, outcome: "completed" });
	const first = handlers.agent_before_settle({ context: { canContinue: false }, outcome: "completed" });
	assert.ok(first?.continue, "empty last turn must trigger a continuation");
	handlers.turn_end({ message: done, context: { canContinue: false }, outcome: "completed" });
	assert.equal(handlers.agent_before_settle({ context: { canContinue: false }, outcome: "completed" }), undefined);
});

test("loop breaker forgets repeats once an edit, write, or bash call may have changed the result", () => {
	const guard = createLoopBreaker(20, 5);
	const read = { toolName: "read", input: { path: "x" } };
	for (let i = 0; i < 5; i++) assert.equal(guard(read), undefined);
	assert.equal(guard({ toolName: "edit", input: { path: "x", edits: [] } }), undefined);
	assert.equal(guard(read), undefined, "a re-read after an edit is not a repeat");
	for (let i = 0; i < 4; i++) assert.equal(guard(read), undefined);
	assert.ok(guard(read).block, "five unbroken repeats after the edit still trip it");
});

test("an edit/test loop never trips the loop breaker", () => {
	const guard = createLoopBreaker(20, 5);
	for (let i = 0; i < 12; i++) {
		assert.equal(guard({ toolName: "edit", input: { path: "a.py", edits: [{ oldText: String(i) }] } }), undefined);
		assert.equal(guard({ toolName: "bash", input: { command: "uv run --offline pytest -q" } }), undefined);
	}
});

test("empty-final nudge leaves aborted or errored turns alone", async () => {
	const { createEmptyFinalNudge } = await import("./mellum-guards.ts");
	const nudge = createEmptyFinalNudge(3);
	const content = [{ type: "thinking", thinking: "..." }];
	assert.equal(nudge({ role: "assistant", stopReason: "aborted", content }), undefined);
	assert.equal(nudge({ role: "assistant", stopReason: "error", content }), undefined);
	assert.ok(nudge({ role: "assistant", stopReason: "stop", content }).continue);
});
