# Mellum independent-runtime research brief

**Date:** 2026-10-07  
**Question:** Are the observed failures introduced by Q6 conversion or MLX?  
**Scope:** Run the original Mellum2.1 Thinking weights directly with llama.cpp, using the same rendered prompts as the earlier MLX BF16/Q6 comparison. No server or generated tool execution is involved.

## Findings

1. **Claim:** The independent reference uses the original Mellum2.1 weights without weight quantization.
   - **Evidence:** Converted the cached safetensors checkpoint at revision `6f239041e7c79166f75f6788dbf7d1971fe1db89` with llama.cpp's `--outtype bf16` converter. The converter and installed inference binary both use build 9580, commit `b4e3dc613baa92a3884d4151e3d631395c81934a`. Ordinary matrices are BF16; some norms and router tensors are stored as F32. The cached Mellum2 GGUF was excluded because it is a different model version.
   - **Source:** [Independent comparison evidence](2026-10-07-mellum-independent-runtime-evidence.json) — local experiment, 2026-10-07; `runtime` and `model`. [Mellum converter](https://github.com/ggml-org/llama.cpp/blob/b4e3dc613baa92a3884d4151e3d631395c81934a/conversion/mellum.py) — ggml-org, accessed 2026-10-07; expert tensor merging and GGUF parameters.
   - **Assessment:** Fact. This is a separate diagnostic GGUF, not a replacement for the existing Q6 MLX checkpoint.

2. **Claim:** Prompt tokenization and the hybrid attention configuration match the intended comparison.
   - **Evidence:** Compared every prompt token from llama.cpp's verbose token dump with the original tokenizer's token IDs: 22 tokens for arithmetic, 24,299 for telemetry, and 50,000 for retrieval. Their SHA-256 hashes match the earlier MLX runs. GGUF metadata preserves 21 sliding-attention layers with window 1,024 and seven full-attention layers; full-attention YaRN factor 16, original context 8,192, theta 500,000, beta values 32/1, and attention factor approximately 1.277259. Inference uses native hybrid caches, BF16 keys and values, 512-token batches, flash attention, and no context shifting.
   - **Source:** [Independent comparison evidence](2026-10-07-mellum-independent-runtime-evidence.json) — local experiment, 2026-10-07; `model.gguf_metadata`, `runtime`, and each check's token equality/hash. [Mellum graph](https://github.com/ggml-org/llama.cpp/blob/b4e3dc613baa92a3884d4151e3d631395c81934a/src/models/mellum.cpp) — ggml-org, accessed 2026-10-07; sliding-layer RoPE and hybrid cache selection.
   - **Assessment:** Fact about the recorded inputs and settings; this does not imply identical floating-point numerics between runtimes.

3. **Claim:** The 50k greedy retrieval failure also occurs outside MLX.
   - **Evidence:** Original BF16 in llama.cpp exhausted the same 4,096-token output allowance without closing its thinking block or returning both `orchid7381` and `maple4627`. It retrieved the early constant but repeatedly reasoned that the late constant was absent. A further run with temperature 1, top-p 0.95, top-k 20, seed 42 also exhausted 4,096 tokens without closing thinking or answering, and misremembered the early constant as `orchid7327`. Short arithmetic returned `4`. Original BF16 and Q6 in MLX had already failed the same greedy retrieval check.
   - **Source:** [Independent comparison evidence](2026-10-07-mellum-independent-runtime-evidence.json) — local experiment, 2026-10-07; both `50k-code-document` checks and `short-arithmetic`. [Earlier BF16/Q6 comparison](2026-10-07-mellum-bf16-q6.md) — local experiment, 2026-10-07; findings 3–5.
   - **Assessment:** Fact. Neither Q6 quantization, MLX, nor oMLX is necessary to produce this failure. It is not confined to greedy decoding, although one sampled run cannot establish its frequency.

4. **Claim:** Skill/path confusion also occurs with unquantized weights in an independent runtime.
   - **Evidence:** The greedy reconstructed telemetry continuation emitted a valid `read` of the existing pi-subagents skill, while continuing to focus on skill invocation. At temperature 1, top-p 0.95, top-k 20, seed 42 invented `/Users/pauleveritt/.pi/agent/git/github.com/obra/superpowers/skills/pi-subagents/SKILL.md`, which does not exist. Seeds 43 and 44 selected existing brainstorming and pi-subagents paths. All calls were `read`; none called an unregistered agent in these independent runs. The original BF16 MLX comparison did produce an unregistered-agent call in one of three sampled continuations.
   - **Source:** [Independent comparison evidence](2026-10-07-mellum-independent-runtime-evidence.json) — local experiment, 2026-10-07; telemetry checks, `tool_calls`, and `read_paths`. [Earlier BF16/Q6 comparison](2026-10-07-mellum-bf16-q6.md) — local experiment, 2026-10-07; finding 4.
   - **Assessment:** Fact about these continuations. The independent runtime reproduces the broader confusion, not the exact historical unknown-agent loop.

## Open questions and limits

| Check | Original BF16 in MLX | Q6 in MLX | Original BF16 in llama.cpp |
| --- | --- | --- | --- |
| Short arithmetic, greedy | Correct `4` | Correct `4` | Correct `4` |
| Telemetry continuation, greedy | Existing brainstorming skill path | Existing brainstorming skill path | Existing pi-subagents skill path |
| Telemetry continuation, temperature 1, three seeds | One unregistered-agent call | Two nonexistent skill paths | One nonexistent skill path |
| 50k retrieval, greedy, 4,096-token allowance | Exhausted allowance in thinking | Exhausted allowance in thinking | Exhausted allowance in thinking |
| 50k retrieval, temperature 1, seed 42 | Not tested | Not tested | Exhausted allowance in thinking |

- These are controlled continuations of reconstructed telemetry. Captured system sections omit the original bootstrap, and Pi messages were translated into OpenAI-style messages. They are not an exact replay of the original request or complete failed session.
- No generated tools were executed. An existing skill path and syntactically valid tool call do not establish that the model answered the user's challenge or chose the right workflow.
- Three telemetry seeds cannot establish error rates or measure Q6's quality cost. Runtime numerics and random-number generators differ; equal seeds do not produce equivalent sampling paths.
- The retrieval prompt is synthetic and repetitive. A 4,096-token allowance does not reproduce the model card's agentic evaluation protocol, which allows up to 16k tokens per turn. These results do not establish universal long-context failure.
- llama.cpp is an independent implementation, not JetBrains' documented vLLM serving stack. Agreement across runtimes strengthens the original-model/decoding explanation; it is not proof that every implementation is defect-free.
- BF16 diagnosis ran on the 128GB M5 Max. It is not the 16GB serving configuration.

## Recommendation

Reject a **Q6-conversion-only explanation** with high confidence. The sampled
MLX transform matches the intended quantization, and unquantized inference in
two runtimes exhibits relevant failures. The evidence now favors behavior of
the original Thinking model under these prompts and decoding settings, plus
its interaction with the skill/tool instructions. A shared MLX defect is no
longer needed to explain the greedy retrieval result. Switching to sampling
also failed in the single independent retrieval run; it is not an established
fix.

Keep the current Q6 files while investigating prompt/tool design and decoding.
Do not expect rebuilding the same weights or increasing weight precision alone
to repair these failure classes. To assess the exact historical agent loop,
use the captured bootstrap and native harness messages for a bounded multi-turn
replay, and score tool decisions separately from retrieval and completed answers.

## Files and reproduction

New diagnostic file:

```text
~/.cache/huggingface/hub/Mellum2.1-12B-A2.5B-Thinking-BF16.gguf
```

The existing MLX directory remains:

```text
~/.cache/huggingface/hub/Mellum2.1-12B-A2.5B-Thinking-6bit
```

Rendered prompts, token IDs, converter logs, raw inference logs, and the sampled
telemetry runner are retained under `/tmp/mellum-independent-reference/`.
Generated outputs are also embedded in the evidence JSON. Use
`llama-completion --binary-file` for these rendered prompts: this release's
`llama-cli` is conversational, and `--file` removes the final newline. Neither
behavior was included in the reported matched results. Failed setup attempts
were discarded before the matched comparisons.

## Recovery follow-up, 2026-10-07

The [recovery report](mellum-recovery-2026-10-07/report.md) extends these findings.
The original retrieval still failed with a 16,384-token native thinking budget;
no-thinking produced incorrect duplicates. Other approximately 50k prompts
succeeded, so this is not a universal hard context cutoff. Runtime differences
on position/content controls remain unresolved.

A clean headless Pi profile with thinking enabled and literal file searches
recovered the original document, all nine values in three new large fixtures,
and a small coding task with independently passing unchanged tests. The report
and portable bundle preserve settings, outputs, reproducers, and the remaining
canonical-vLLM and historical-replay questions. No weights or filenames changed.
