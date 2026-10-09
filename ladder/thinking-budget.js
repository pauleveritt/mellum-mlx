// Make Pi's thinking level mean something on oMLX. Pi sends no thinking control to an
// openai-completions provider (ablation A5: "high" and "medium" produced identical requests);
// oMLX honours a top-level `thinking_budget` per request (request > model settings) and
// `chat_template_kwargs.enable_thinking`. Load BEFORE record-pi.js so the trace shows it.
export const BUDGETS = { minimal: 512, low: 1024, medium: 2048, high: 4096, xhigh: 8192 };

export function applyThinkingLevel(payload, level) {
  if (!payload) return payload;
  if (level === "off") {
    return { ...payload, chat_template_kwargs: { ...(payload.chat_template_kwargs || {}), enable_thinking: false } };
  }
  const budget = BUDGETS[level];
  if (budget === undefined) return payload; // "max" or unknown: no cap
  return { ...payload, thinking_budget: budget };
}

export default function (pi) {
  pi.on("before_provider_request", (event, ctx) => applyThinkingLevel(event.payload, ctx?.thinkingLevel));
}
