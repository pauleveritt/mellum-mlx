# Mellum 2.1 MLX

Convert [Mellum 2.1 Thinking](https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking)
to MLX and serve it with [oMLX](https://github.com/jundot/omlx), preserving its native hybrid cache.

## Recommended path

Use the existing **6-bit affine MLX conversion, group size 64**, with the native
BF16 cache and one active request. Mellum's conversion policy keeps the MoE routers
at 8 bits. Weight quantization does not change the cache precision or attention layout.

The converted model is published at
<https://huggingface.co/pauleveritt/Mellum2.1-12B-A2.5B-Thinking-mlx-6bit> (9.9 GB,
two safetensors shards) and lives locally at:

```text
~/.cache/huggingface/hub/Mellum2.1-12B-A2.5B-Thinking-6bit
```

Pull it with `hf download pauleveritt/Mellum2.1-12B-A2.5B-Thinking-mlx-6bit` instead
of reconverting.

## Using it as a coding agent: Mellum Worker and Mellum Mode (shipped 2026-10-09)

Mellum could not run the full Superpowers workflow as the primary agent
([recovery report](docs/research/mellum-recovery-2026-10-07/report.md)). The
measured answer is to run it as a narrowly configured worker under Pi, in one
of two ways, both documented in **[docs/mellum-worker.md](docs/mellum-worker.md)**:

- **Mellum Worker** (`mellum-worker`), a pi-subagents child (`.pi/agents/mellum-worker.md`): your
  usual model stays the parent, scopes the task, briefs the child, and runs the
  tests itself. 15/15 on the five-rung ladder.
- **Mellum Mode** (`/mellum <task>`, `.pi/mellum/mellum-mode.ts`): the same worker
  inside your own session, no parent round trip. 14/15 in the operator profile, against
  10/15 for Mellum as the primary agent in that profile and 8/15 in bare Pi.

The worker is a 643-character prompt of facts about the test command, the seven
file tools, and a guard extension (an empty-turn nudge capped at three, a loop
breaker). Every part was measured in and out; the scoreboard is
[docs/research/ladder/ablation-summary.md](docs/research/ladder/ablation-summary.md),
each phase has its record under `docs/research/ladder/`, and the runner is
`uv run python -m ladder.run_ladder`. Follow-ups are scheduled in
[docs/research/2026-10-09-future-work.md](docs/research/2026-10-09-future-work.md).

What the measurements settled: the request cap must be 16,384 tokens (Pi sends
it; the server profile is overridden); the presence penalty, server thinking
budget and tool-result cap are inert; Pi's thinking level never reaches oMLX;
a request-level `thinking_budget` is not enforced for this model; stripping
earlier turns' thinking from context makes runs 60% slower because on this
cached local server generation, not prefill, is the cost. The
[OpenCode follow-up](docs/research/mellum-recovery-2026-10-07/opencode-report.md)
predates the recipe. The OpenCode port shipped in
<https://github.com/pauleveritt/mellum-worker> (v0.1.1): the same v5 prompt as
an OpenCode subagent, smoke-tested but not measured on the ladder.

### Preserve the hybrid cache

Mellum uses 28 attention layers:

- 21 sliding-window layers use `RotatingKVCache` with a 1,024-token window.
- 7 full-attention layers use `KVCache` and retain the whole sequence.

The model configuration keeps this layout and its native 131,072-token context
limit. The installed oMLX 0.6.4 includes a Mellum implementation through its bundled
MLX-LM 0.31.3. No custom runner or rotating-cache implementation is needed for the
native cache path. Leave cache quantization disabled.

### Serve through oMLX

The existing menu bar server is configured and running at `http://127.0.0.1:8001`.
For an alternative CLI launch, point oMLX at the **parent directory** containing the model folder:

```bash
omlx serve \
  --model-dir "$HOME/.cache/huggingface/hub" \
  --host 127.0.0.1 \
  --port 8001 \
  --max-concurrent-requests 1 \
  --hot-cache-max-size 0 \
  --memory-guard-gb 14
```

oMLX scans model subdirectories; pointing `--model-dir` at the model folder itself
will not discover it. With the menu bar app, add the same parent directory in its
model-directory settings and apply the equivalent concurrency and memory settings.
Use either the app or a CLI server on port 8001.

Open `http://127.0.0.1:8001/admin`, select
`Mellum2.1-12B-A2.5B-Thinking-6bit`, and set:

| Setting | Starting value |
| --- | --- |
| Maximum context window (`max_context_window`) | 56,000 tokens |
| Maximum generation tokens (`max_tokens`) | 16,384 tokens (Pi sends its own `max_tokens`, which overrides this; a 4,096 cap cut a three-file run off mid-thought) |
| TurboQuant KV cache | Disabled |

Budget up to 50,000 **tokenized prompt tokens**, including chat history and template
overhead, plus the generated tokens; the ladder's largest worker request was
about 20,000 tokens. Thinking tokens consume the generation
budget too. The 56,000-token serving limit leaves space for both; keep the model's
RoPE and sliding-window configuration unchanged.

Start with only Mellum loaded and the RAM hot cache disabled. The memory guard
value of 14 is interpreted as 14 GiB by this oMLX version; it is a starting ceiling
for the 16GB budget, not a guarantee that every request will fit. SSD prefix caching
can remain available for reuse between requests; active attention still needs its
native KV state in memory.

### Validate the serving path

First confirm the model appears in `/v1/models`, then make a short request to
`/v1/chat/completions` using the model ID above. Follow with a 50,000-token prompt
and the intended generation length. Check output correctness, reported token counts,
peak memory, and any memory-guard rejection before increasing concurrency.

The conversion has already passed standalone MLX generation and a 50,000-token
prompt run with prefill chunks of 512 and 32 generated tokens:

| Measurement | Result |
| --- | --- |
| Converted weight shards | 9.195 GiB |
| MLX peak memory | Approximately 10.42 GiB (11.186 GB) |

On the same M5 Max, oMLX subsequently completed a cold 50,000-token prompt and
4,096 generated tokens in 48.18 seconds. Its sampled physical memory peaked at
11.74 GiB, below the configured 14 GiB guard. Short arithmetic requests returned
correct answers before and after the long runs.

**Serving capacity is verified; long-context retrieval quality is not.** Two
synthetic 50k retrieval checks failed, and direct MLX generation also failed the
same code-document retrieval check. This does not identify an oMLX-only fault or
prove the cause. The checks are not a general model-quality benchmark. Measurements
on this 128GB machine also do not establish behavior on a machine with 16GB total
shared memory. See the [serving validation record](docs/research/2026-10-07-mellum-omlx-native-cache.md).

A later [matched comparison with original BF16 weights](docs/research/2026-10-07-mellum-bf16-q6.md)
reproduced retrieval and tool-selection failure classes under MLX without
quantization. A subsequent [independent llama.cpp comparison](docs/research/2026-10-07-mellum-independent-runtime.md)
also reproduced the 50k retrieval failure with original BF16 weights, using
identical prompt tokens and native hybrid caches. One sampled telemetry
continuation invented a nonexistent skill path. This rules out a
Q6-conversion-only explanation and favors original-model behavior under these
prompts and settings. The exact historical agent loop remains untested.

## Reproduce the conversion

Use Python 3.14 and `uv`. The script reads the original unquantized safetensors
checkpoint from the HF cache offline; GGUF files are not its input.

```bash
uv sync --locked
uv run main.py --check
uv run main.py --bits 6 \
  --output "$HOME/.cache/huggingface/hub/Mellum2.1-12B-A2.5B-Thinking-6bit"
```

The existing conversion does not need to be repeated. The final command is for
reproduction when the output directory does not exist; the script refuses to
overwrite it. Supply `--source /path/to/checkpoint` to select a local source
explicitly. Always supply `--output` for this storage location: the script's current
default remains `~/models/Mellum2.1-12B-A2.5B-Thinking-Nbit`.
