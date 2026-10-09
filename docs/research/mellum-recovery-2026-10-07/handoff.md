# Research handoff: Mellum 2.1 Thinking

## Start here

User objective: a usable Mellum 2.1 MLX model with native hybrid cache, initially
targeting a 16GB memory budget and 50k prompt. Investigate the failed agent
session, isolate model versus conversion/runtime causes, iterate toward a
workaround, and leave shareable evidence. The user authorized headless Pi,
direct inference, llama.cpp installation, and smaller/different context tests.
Exclude caix and TurboQuant. Preserve existing weights and global Pi/oMLX
configuration. Do not send this report to anyone on the user's behalf.

Read [report.md](report.md), [README.md](README.md), and
[evidence.json](evidence.json). The bundle is portable and excludes private
historical session messages. Model names are unchanged:

- MLX: `~/.cache/huggingface/hub/Mellum2.1-12B-A2.5B-Thinking-6bit`.
- Original HF snapshot: `models--JetBrains--Mellum2.1-12B-A2.5B-Thinking/snapshots/6f239041e7c79166f75f6788dbf7d1971fe1db89` inside that cache.
- Diagnostic reference: `~/.cache/huggingface/hub/Mellum2.1-12B-A2.5B-Thinking-BF16.gguf`.

The existing endpoint is `http://127.0.0.1:8001/v1`. Original BF16 tests ran on
a 128GB M5 Max; no physical 16GB configuration was tested. The reference GGUF
is 24,311,970,080 bytes and is not suitable for the 16GB operating goal.

## Established findings; avoid repeating the entire matrix

Read the [OpenCode follow-up](opencode-report.md) and
[scoped SQLite evidence](opencode-evidence.json) before extending the harness
comparison. Clean OpenCode completed conversation, nine-value file retrieval,
and coding checks. Configured Superpowers OpenCode also completed the corrected
conversation, with unnecessary brainstorming on greeting. `--pure` alone
removed that call. This strengthens the operating workaround while leaving
the full historical loop unresolved. Use explicit `--dir`, canonical paths,
and final-message/tool-state checks; exit zero and reasoning usage zero can
both mislead. Read only scoped sessions; never share the complete SQLite DB.

Later [look-around evidence](opencode-look-around-evidence.json) adds a limit:
the clean profile inspected files without a skill call, but “Why did you load
superpowers?” triggered an irrelevant website fetch through allowed bash and a
misleading answer. Do not describe skill isolation as a full task-routing fix.
Tool policy, task correctness, and truthful reporting require separate scores.

1. Original BF16 and Q6 MLX both exhaust 4,096 tokens inside thinking on the
   original 50k retrieval prompt. Original BF16 llama.cpp does too, including
   one sampled trial. Raising native output to 16,384 still fails. Turning off
   thinking returns incorrect duplicates in all three tested model/runtime
   configurations.
2. This is not a universal 50k cutoff: the repetitive 49,993-token control
   passes in Q6 MLX, BF16 MLX, and BF16 llama.cpp. The Q6 length series passes
   at seven lengths from 965 to 49,993 tokens. Diverse 24k controls pass in Q6;
   corresponding 50k controls fail.
3. Moving both original constants to roughly 10%/90% succeeds in BF16 and Q6
   MLX but fails in BF16 llama.cpp. The BF16 diverse C++ control fails by literal
   capitalization (`SPruce50171`) while returning the correct second value;
   Q6 and native failures are more severe. Preserve these distinctions.
4. Configuration/tokenizer/template and sampled exact quantization packing
   audits passed. This rejects a Q6-only explanation, not every possible
   transform/runtime defect. No full-tensor audit or canonical vLLM comparison
   has been completed.
5. Clean Pi + thinking + literal file searches works. Original file: both
   values exact. Three new large files with decoys: all nine exact, zero tool
   errors under greedy decoding. Three sampled seeds: all final values exact;
   seed 44 recovered after one wrong-path error and a literal-regex mismatch.
6. Clean thinking Pi answers greeting, README summary, and methodological
   challenge appropriately. Thinking-off Pi returns analysis on the challenge.
   Keep thinking enabled for agent work. Small coding fix passes all three
   independent tests with tests unchanged. Packaged runners also passed.

## Evidence navigation

| JSON key | Contents |
| --- | --- |
| `provenance` | Pinned model/runtime, converter dependencies, hybrid cache/RoPE metadata |
| `conversion_audit` | Configuration equality and sampled weight/packing checks |
| `earlier_thinking_mlx`, `earlier_thinking_native` | Earlier matched original 50k failures and arithmetic control; private telemetry omitted |
| `mlx_q6_matrix` | Eleven length/content tests |
| `mlx_q6_followups` | Eight instruction/position/content controls |
| `mlx_bf16_controls` | Four matched original-weight controls |
| `native_controls` | Five native trials with matching token hashes, raw outputs, generation counts |
| `pi_runs` | Eighteen trials; finals, tools/results, actual request kwargs, context sizes, guard interruptions |
| `portable_checks` | Independent execution of the packaged direct/Pi runners |
| `coding` | Initial failing tests and independent post-fix test log |

`cases.json.gz` contains twenty direct prompts. Pi retrieval goldens and disk
fixtures are separate. Direct results use exact case-sensitive value/order
scoring with flexible separators. Pi goldens use exact final-string scoring.
Always check authoritative `message_end`, final stop reason, and tools; Pi JSON
process exit zero alone does not prove a completed or useful response.

## Next experiment: canonical original-weight reference

Use an appropriate accelerator host for the documented vLLM stack, original
Thinking checkpoint, and Hermes tool parser. Consult the pinned model card
linked in the report for supported settings. First compare token IDs for the
exact bundled message/template inputs. A model-family or chat-template change
invalidates a matched comparison.

Prioritize these five bounded controls rather than another broad sweep:

1. `legacy-50k-thinking`, greedy, 4,096 and 16,384 generated tokens.
2. The same thinking prompt with model-card agentic sampling (temperature 1,
   top-p .95, top-k 20), multiple seeds and 16k output budget.
3. `repetitive-50000-no-thinking`, a positive control. If disabling thinking is
   unsupported, also render a thinking version and label it separately.
4. `legacy-move-both`, to investigate the MLX/native disagreement.
5. `diverse-safe-50000`, checking exact case and both values, not only semantic
   similarity.

Separate scores: correct literals, closed thinking, substantive final answer,
and budget exhaustion. Record logits or top-token probabilities at divergence
if practical. A native greedy comparison should match prompt tokens and
attention/RoPE settings; equal seeds in different sampling implementations
are not equivalent random streams.

If vLLM fails the original prompt too, evidence for a model/prompt limitation
strengthens. If vLLM succeeds consistently, investigate MLX/llama.cpp hybrid
attention and YaRN against that reference before blaming weights. Do not change
RoPE, sliding-window size, or cache type speculatively and call that a repair.

## Next experiment: real agent workflow

The full historical loop remains unresolved. The synthetic three-turn
conversation is a smoke test, not an exact replay. To test the historical case,
obtain its complete bootstrap/native messages from the user's retained local
session, preserve privacy, and build a bounded replay. Do not put those messages
in a public reproduction archive.

Begin with the working clean profile. Add one workflow component at a time:
context files, skills, Superpowers extension, then subagent/supervisor machinery.
Keep model/settings fixed. Check whether skill identifiers become agent names,
whether explicit errors trigger correction, whether request IDs are preserved,
and whether the user gets a substantive final answer. Validate the harness's
registered agents and tool schemas separately. This has not been implemented
or tested end to end.

For stronger workaround confidence, test representative multi-file tasks with
bounded search/read output, decoys, realistic edit failures, and unchanged
independent tests. The existing coding fixture is intentionally small; do not
extrapolate broad SWE capability from it. Validate any context policy on the
actual task distribution rather than claiming a universal 24k safe limit.

## Local-only provenance and implementation cautions

On the original workstation, scratch outputs reside under
`/tmp/mellum-recovery-20261007`, with older reference data under
`/tmp/mellum-independent-reference` and `/tmp/mellum-quant-comparison-20261007`.
These directories are temporary; portable outputs in this bundle are the
durable handoff. Earlier briefs sit beside this directory in the repository.

- Use `llama-completion --binary-file`. In the tested build `llama-cli` is
  conversational, and `--file` strips the final newline.
- Transformers 5.19 template calls need `return_dict=False` when expecting a
  token list. The packaged runner fixes this and verifies native tokens.
- Native caches: 21 `RotatingKVCache` / seven `KVCache`; no cache quantization.
- Do not use `usage.reasoning == 0` to infer thinking off; inspect template kwargs
  and actual response blocks.
- External diagnostic guards caused early retrieval/coding aborts. Label them
  separately from model-only failures. The final portable Pi policy treats any
  tool error as a failing run even if the model recovers its final answer.
- Some timings/memory observations overlap other runs; they are not performance
  benchmarks. The earlier isolated serving-capacity result belongs to a
  separate validation, not these quality experiments.
- Preserve unrelated repository changes; no commit was created for this work.

The practical operating workaround is complete. Fundamental attribution,
full historical replay, broad task reliability, and physical 16GB verification
remain open research questions.
