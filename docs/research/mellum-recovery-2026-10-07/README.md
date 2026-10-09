# Mellum recovery reproduction bundle

Read [report.md](report.md) for conclusions and [handoff.md](handoff.md) for
further research. [evidence.json](evidence.json) records the observed outcomes.
The bundle contains no model weights or private historical messages.

An [OpenCode follow-up](opencode-report.md) now includes SQLite telemetry,
[a clean configuration](opencode-clean.json), `run_opencode.mjs`, and
`inspect_opencode.mjs`. Clean OpenCode also passed the nine-value retrieval
battery and the coding fixture; its configured conversation completed too,
despite an unnecessary brainstorming call on greeting.

## Direct MLX and llama.cpp

The original tokenizer/checkpoint defaults to the HF cache snapshot at revision
`6f239041e7c79166f75f6788dbf7d1971fe1db89`. The MLX model default is
`~/.cache/huggingface/hub/Mellum2.1-12B-A2.5B-Thinking-6bit`; the native default
is `~/.cache/huggingface/hub/Mellum2.1-12B-A2.5B-Thinking-BF16.gguf`. Override
`--tokenizer` and `--model` for another local location. Use the 2.1 Thinking
checkpoint, not a Mellum2 checkpoint with a similar filename.

Run from this bundle directory. The local project environment has the recorded
MLX versions; on another Apple Silicon machine, use an isolated environment:

```bash
uv venv --python 3.14 .venv-repro
uv pip install --python .venv-repro/bin/python \
  mlx==0.32.3 mlx-lm==0.32.0 transformers==5.19.0
PYTHON=.venv-repro/bin/python
"$PYTHON" reproduce.py --list
"$PYTHON" reproduce.py --case repetitive-1000-no-thinking
"$PYTHON" reproduce.py --case legacy-50k-no-thinking-mlx
"$PYTHON" reproduce.py --case legacy-50k-thinking --max-tokens 4096
```

To test original BF16 in MLX, pass `--model /path/to/original/snapshot`.
The same script runs llama.cpp without MLX imports; that path only needs
Transformers for tokenization. Install/build the pinned llama.cpp revision with
Mellum support and put `llama-completion` on PATH, or supply `--llama-binary`.

```bash
"$PYTHON" reproduce.py --backend llama --case repetitive-50000-no-thinking
"$PYTHON" reproduce.py --backend llama --case legacy-50k-thinking --max-tokens 16384
"$PYTHON" reproduce.py --backend llama --case legacy-move-both
"$PYTHON" reproduce.py --backend llama --case diverse-safe-50000
```

Original BF16 is a diagnostic configuration requiring more than 16GB. The
diagnostic GGUF was produced using the pinned llama.cpp `convert_hf_to_gguf.py`
with `--outtype bf16`, torch 2.11.0, and transformers 5.19.0. Transformers 5.5.3
failed nested RoPE validation during setup; it was not used for the final GGUF.
If rebuilding it, use an isolated converter environment and a new output path.
Weights and the llama.cpp converter itself are not in this archive.

`converter_snapshot.py` is a byte-for-byte copy of this project's MLX conversion
script, included so the transform can be reviewed. It reads original
safetensors offline and refuses to overwrite an existing output. The installed
MLX-LM Mellum quantization policy supplies eight-bit routers. To reproduce in a
new output directory with the environment above:

```bash
hf download JetBrains/Mellum2.1-12B-A2.5B-Thinking \
  --revision 6f239041e7c79166f75f6788dbf7d1971fe1db89
"$PYTHON" converter_snapshot.py --source /path/to/pinned/snapshot --check
"$PYTHON" converter_snapshot.py --source /path/to/pinned/snapshot --bits 6 \
  --output /path/to/new/Mellum2.1-12B-A2.5B-Thinking-6bit
```

The first command downloads the checkpoint if it is not already cached. Do not
repeat conversion into the existing model directory; its weights are preserved.

`--case` is repeatable. Optional flags include `--thinking on|off`,
`--temperature 1`, `--seed`, `--max-tokens`, `--output`, and `--context-size`.
Thinking overrides change the rendered prompt hash. The default native context
allocation is 65,536 tokens; it grows when prompt plus output requires more.
No context shifting or cache quantization is used.

Each result includes input token hash/count, generated text, extracted final
answer, and `passed`. **A completed diagnostic process can exit zero with a
failed retrieval score.** Native prompt mismatches raise errors. Direct scoring
requires exact literals and ordering but tolerates punctuation between them.
This runner is an experiment harness, not a replacement model server.

## Headless Pi against the existing server

Requires Node, Pi 1.0.2 on PATH, ripgrep, and an OpenAI-compatible local server
with Mellum tool/thinking support. Pi's `find` additionally requires `fd`.
For the recorded version, install Pi in a separate tool environment if needed:

```bash
npm install --global @earendil-works/pi-coding-agent@1.0.2
pi --version
node run_pi.mjs retrieval
node run_pi.mjs coding
node run_pi.mjs conversation
```

The runner creates a new temporary agent profile and sandbox each time; it does
not change global Pi settings. It disables automatic extensions, skills, context
files, prompt templates, and themes, then explicitly loads `record-pi.js` to log
diagnostic requests and tool outcomes. No automatic subagents are used.

Defaults: `http://127.0.0.1:8001/v1`, model ID
`Mellum2.1-12B-A2.5B-Thinking-6bit`, thinking `high`, temperature 0, 4,096 output
tokens, advertised context 56,000 to match the existing oMLX serving limit.
The script configures compatibility with Qwen-style thinking template flags.
The server must honor them and support tools; these are not guaranteed for an
arbitrary OpenAI-compatible endpoint.

```bash
MELLUM_FIXTURE_SEED=202 node run_pi.mjs retrieval
MELLUM_FIXTURE_SEED=303 node run_pi.mjs retrieval
MELLUM_TEMPERATURE=1 MELLUM_SEED=44 node run_pi.mjs retrieval
MELLUM_THINKING=off node run_pi.mjs conversation
MELLUM_BASE_URL=http://127.0.0.1:8001/v1 \
  MELLUM_MODEL_ID=Mellum2.1-12B-A2.5B-Thinking-6bit node run_pi.mjs retrieval
```

A summary prints `runDir`; it contains the temporary profile, fixture workspace,
final summary, authoritative event logs, request/tool traces, and independent
coding-test output. Retrieval is checked against an exact one-line golden.
Coding is independently tested and checked for unchanged tests. Conversation
finals need semantic review; exit zero alone does not establish answer quality.
An external 12-request guard and three-minute timeout per turn bound the runner.
These bounds are diagnostic controls, not model errors. The runner returns
nonzero for process errors, abnormal final stop, tool errors, a retrieval
mismatch, or a failed coding verification. A sampled answer may recover after a
tool error and still receive nonzero under this strict runner policy.

The bundled coding fixture is deliberately buggy. Its initial tests should
fail. Pi receives a copy in a temporary sandbox; packaged tests stay unchanged.

## Use the clean profile for a real task

After a runner prints `runDir`, its profile can be reused for a bounded task in
your own project. Substitute that printed directory below:

```bash
RUN_DIR=/path/from/the/printed/runDir
cd /path/to/your/project
PI_CODING_AGENT_DIR="$RUN_DIR/pi-agent" PI_OFFLINE=1 pi \
  --no-extensions --no-skills --no-prompt-templates --no-themes \
  --no-context-files --provider mellum-diagnostic \
  --model Mellum2.1-12B-A2.5B-Thinking-6bit --thinking high \
  --tools read,edit,grep,find,ls,bash
```

That launch has no diagnostic capture extension or request-count guard. Specify
precise file paths and search terms; retrieve focused snippets before reasoning
about them. Starting a fresh session for a separate task avoids accumulating
unneeded history. This is a tested starting profile, not a guarantee for every
task or for the historical Superpowers workflow.

## Package integrity and data sources

`cases.json.gz` contains twenty fully specified prompts with token hashes and
goldens. `pi-goldens.json` describes the three file-retrieval fixtures.
Synthetic Python documents are data, not executable examples. Diverse direct
prompts include source fragments from pinned llama.cpp under
[its MIT license](fixtures/LLAMA_CPP_LICENSE). Use `manifest.sha256` to verify
every packaged file other than the manifest itself:

```bash
shasum -a 256 -c manifest.sha256
```

Runtime timings and memory in the evidence are retained observations; some runs
overlapped. The anonymized `<HOME>` and `<WORKDIR>` fields identify original
local paths, not paths that should be copied into a reproduction command.
