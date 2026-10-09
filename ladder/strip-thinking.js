// Drop earlier turns' reasoning from the outgoing payload. With preserve_thinking the
// request otherwise carries every prior assistant message's reasoning_content, which in a
// late rung-5 request was 70% of the payload (docs/research/2026-10-09-worker-cost-options.md).
// Load this BEFORE record-pi.js so the trace shows what was actually sent.
export function stripPriorReasoning(payload) {
  if (!payload || !Array.isArray(payload.messages)) return payload;
  const messages = payload.messages.map(m => {
    if (m.role !== 'assistant') return m;
    const { reasoning_content, reasoning, ...rest } = m;
    return rest;
  });
  return { ...payload, messages };
}
export default function (pi) {
  pi.on('before_provider_request', event => stripPriorReasoning(event.payload));
}
