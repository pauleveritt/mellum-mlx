import assert from "node:assert/strict";
import test from "node:test";
import { applyThinkingLevel } from "./thinking-budget.js";

test("medium sets a 2048-token thinking_budget and leaves the rest alone", () => {
	const p = { model: "m", messages: [], chat_template_kwargs: { enable_thinking: true } };
	const out = applyThinkingLevel(p, "medium");
	assert.equal(out.thinking_budget, 2048);
	assert.deepEqual(out.messages, []);
	assert.equal(p.thinking_budget, undefined, "input not mutated");
});

test("off disables thinking through chat_template_kwargs; max sets no budget", () => {
	assert.equal(applyThinkingLevel({ messages: [] }, "off").chat_template_kwargs.enable_thinking, false);
	assert.equal(applyThinkingLevel({ messages: [] }, "max").thinking_budget, undefined);
});
