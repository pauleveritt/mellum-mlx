"""Reproduce diagnostic prompts; this is a research harness, not a server."""

import argparse
import gzip
import hashlib
import json
import re
import struct
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, cast


BUNDLE = Path(__file__).resolve().parent
HUB = Path.home() / ".cache/huggingface/hub"
REVISION = "6f239041e7c79166f75f6788dbf7d1971fe1db89"
ORIGINAL = HUB / "models--JetBrains--Mellum2.1-12B-A2.5B-Thinking/snapshots" / REVISION


def extract_answer(text: str, *, thinking: bool) -> str:
    if "</think>" in text:
        return text.rsplit("</think>", 1)[-1].split("<|im_end|>", 1)[0].strip()
    if thinking or "<think>" in text:
        return ""
    return text.split("<|im_end|>", 1)[0].split(" [end of text]", 1)[0].strip()


def score(answer: str, expected: list[str]) -> bool:
    # Include incorrectly spelled/capitalized alternatives in the observed list.
    observed = re.findall(r"(?:cedar|willow|birch|juniper|orchid|maple|spruce|hazel)\d+", answer, re.IGNORECASE)
    return observed == expected


def run_case(case: dict[str, Any], args: argparse.Namespace, output: Path) -> dict[str, Any]:
    # Optional backend imports keep --list usable on machines without MLX.
    from transformers import AutoTokenizer, PreTrainedTokenizerBase

    thinking = case["enable_thinking"] if args.thinking is None else args.thinking == "on"
    loaded = cast(object, AutoTokenizer.from_pretrained(args.tokenizer))
    if not isinstance(loaded, PreTrainedTokenizerBase):
        raise TypeError("Expected a Transformers tokenizer")
    tokenizer = loaded
    options = {"add_generation_prompt": True, "enable_thinking": thinking, "return_dict": False}
    tokens = cast(list[int], tokenizer.apply_chat_template(case["messages"], tokenize=True, **options))
    prompt = tokenizer.apply_chat_template(case["messages"], tokenize=False, **options)
    if not isinstance(prompt, str):
        raise TypeError("Expected rendered prompt text")
    prompt_hash = hashlib.sha256(struct.pack(f"<{len(tokens)}i", *tokens)).hexdigest()
    if args.thinking is None:
        assert prompt_hash == case["prompt_sha256"], "Prompt differs from recorded input"
    name = case["name"]
    (output / f"{name}.prompt.txt").write_text(prompt)
    max_tokens = args.max_tokens or case["max_tokens"]
    start = time.monotonic()
    result: dict[str, Any] = {"case": name, "backend": args.backend, "model": str(args.model),
        "thinking": thinking, "temperature": args.temperature, "seed": args.seed,
        "prompt_tokens": len(tokens), "prompt_sha256": prompt_hash, "max_tokens": max_tokens,
        "expected_values": case["expected_values"]}
    if args.backend == "mlx":
        import mlx.core as mx
        from mlx_lm import load, stream_generate
        from mlx_lm.sample_utils import make_sampler

        model, mlx_tokenizer = load(str(args.model))
        assert tokens == mlx_tokenizer.apply_chat_template(case["messages"], tokenize=True, **options)
        mx.random.seed(args.seed)
        sampler = make_sampler(temp=args.temperature, top_p=0.95 if args.temperature else 1,
            top_k=20 if args.temperature else 0)
        parts = []
        response = None
        for response in stream_generate(model, mlx_tokenizer, tokens, sampler=sampler,
            max_tokens=max_tokens, prefill_step_size=512):
            parts.append(response.text)
        if response is None:
            raise RuntimeError("MLX returned no generation events")
        text = "".join(parts)
        result.update(generation_tokens=response.generation_tokens, finish_reason=response.finish_reason,
            cache_types=[type(cache).__name__ for cache in model.make_cache()])
    else:
        context = max(args.context_size, ((len(tokens) + max_tokens + 1023) // 1024) * 1024)
        command = [args.llama_binary, "--model", str(args.model), "--binary-file", str(output / f"{name}.prompt.txt"),
            "--no-conversation", "--no-display-prompt", "--no-escape", "--simple-io", "--special", "--verbose-prompt",
            "--ctx-size", str(context), "--predict", str(max_tokens), "--batch-size", "512", "--ubatch-size", "512",
            "--temp", str(args.temperature), "--seed", str(args.seed), "--top-k", "20" if args.temperature else "0",
            "--top-p", "0.95" if args.temperature else "1", "--min-p", "0", "--repeat-penalty", "1",
            "--no-context-shift", "--no-warmup", "--flash-attn", "on", "--cache-type-k", "bf16", "--cache-type-v", "bf16",
            "--log-verbosity", "4"]
        if args.temperature:
            command += ["--samplers", "top_k;top_p;temperature"]
        with (output / f"{name}.output.txt").open("w") as stdout, (output / f"{name}.log").open("w") as stderr:
            process = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=args.timeout, check=False)
        text = (output / f"{name}.output.txt").read_text()
        log = (output / f"{name}.log").read_text()
        native_tokens = [int(value) for value in re.findall(r"^.*? I\s+(\d+) -> ", log, re.MULTILINE)]
        assert native_tokens == tokens, "llama.cpp tokenization differs"
        assert process.returncode == 0, f"llama.cpp exited {process.returncode}"
        result.update(command=command, process_exit_code=process.returncode,
            finish_reason="eos" if "<|im_end|>" in text else "length")
    answer = extract_answer(text, thinking=thinking)
    result.update(output=text, answer=answer, passed=score(answer, case["expected_values"]),
        elapsed_seconds=round(time.monotonic() - start, 3))
    (output / f"{name}.result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--backend", choices=("mlx", "llama"), default="mlx")
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--model", type=Path)
    parser.add_argument("--tokenizer", type=Path, default=ORIGINAL)
    parser.add_argument("--llama-binary", default="llama-completion")
    parser.add_argument("--thinking", choices=("on", "off"))
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--context-size", type=int, default=65536)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with gzip.open(BUNDLE / "cases.json.gz", "rt") as source:
        cases = json.load(source)["cases"]
    if args.list:
        for case in cases:
            print(f"{case['name']}\t{case['prompt_tokens']} tokens\tthinking={case['enable_thinking']}")
        return
    selected = args.case or ["legacy-50k-no-thinking-mlx"]
    unknown = set(selected) - {case["name"] for case in cases}
    if unknown:
        parser.error(f"Unknown cases: {sorted(unknown)}")
    if args.model is None:
        args.model = HUB / ("Mellum2.1-12B-A2.5B-Thinking-6bit" if args.backend == "mlx"
            else "Mellum2.1-12B-A2.5B-Thinking-BF16.gguf")
    output = args.output or Path(tempfile.mkdtemp(prefix="mellum-direct-"))
    output.mkdir(parents=True, exist_ok=True)
    for case in cases:
        if case["name"] in selected:
            result = run_case(case, args, output)
            print(json.dumps({key: value for key, value in result.items() if key not in {"command", "output"}}))
    print(f"Evidence directory: {output}")


if __name__ == "__main__":
    main()
