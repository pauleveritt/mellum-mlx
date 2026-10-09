import assert from "node:assert/strict";
import test from "node:test";
import { stripPriorReasoning } from "./strip-thinking.js";

test("reasoning_content is removed from every assistant message and nothing else changes", () => {
	const payload = {
		model: "m",
		chat_template_kwargs: { enable_thinking: true, preserve_thinking: true },
		messages: [
			{ role: "system", content: "s" },
			{ role: "user", content: "u" },
			{ role: "assistant", content: "", reasoning_content: "long thoughts", tool_calls: [{ id: "1" }] },
			{ role: "tool", tool_call_id: "1", content: "r" },
			{ role: "assistant", content: "done", reasoning_content: "more" },
		],
	};
	const out = stripPriorReasoning(payload);
	assert.equal(out.messages.length, 5);
	for (const m of out.messages) assert.ok(!("reasoning_content" in m));
	assert.deepEqual(out.messages[2].tool_calls, [{ id: "1" }]);
	assert.equal(out.messages[4].content, "done");
	assert.deepEqual(out.chat_template_kwargs, payload.chat_template_kwargs);
	assert.ok("reasoning_content" in payload.messages[2], "input is not mutated");
});
