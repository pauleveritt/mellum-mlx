import json
import subprocess
import sys
from pathlib import Path

import mlx.core as mx
import pytest
from mlx.utils import tree_flatten
from mlx_lm import load
from mlx_lm.models.cache import KVCache, RotatingKVCache
from mlx_lm.models.mellum import Model, ModelArgs
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from transformers import PreTrainedTokenizerFast


SCRIPT = Path(__file__).resolve().parents[1] / "main.py"


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """A real, small BF16 Mellum checkpoint with Hugging Face expert names."""
    directory = tmp_path / "source"
    directory.mkdir()
    config = {
        "model_type": "mellum",
        "hidden_size": 64,
        "num_hidden_layers": 2,
        "intermediate_size": 128,
        "num_attention_heads": 2,
        "num_experts": 2,
        "num_experts_per_tok": 1,
        "moe_intermediate_size": 64,
        "rms_norm_eps": 1e-6,
        "vocab_size": 64,
        "num_key_value_heads": 1,
        "head_dim": 64,
        "tie_word_embeddings": False,
        "max_position_embeddings": 131072,
        "norm_topk_prob": True,
        "sliding_window": 1024,
        "layer_types": ["sliding_attention", "full_attention"],
        "rope_parameters": {
            "sliding_attention": {"rope_type": "default", "rope_theta": 500000.0},
            "full_attention": {"rope_type": "default", "rope_theta": 500000.0},
        },
    }
    (directory / "config.json").write_text(json.dumps(config))
    mx.random.seed(0)
    model = Model(ModelArgs.from_dict(config))
    weights = {}
    for name, value in tree_flatten(model.parameters()):
        if ".switch_mlp." in name:
            for expert in range(2):
                weights[name.replace("switch_mlp", f"experts.{expert}")] = value[
                    expert
                ].astype(mx.bfloat16)
        else:
            weights[name] = value.astype(mx.bfloat16)
    mx.save_safetensors(str(directory / "model.safetensors"), weights)
    index = {"weight_map": {name: "model.safetensors" for name in weights}}
    (directory / "model.safetensors.index.json").write_text(json.dumps(index))
    vocabulary = {f"token{i}": i for i in range(64)}
    tokenizer = PreTrainedTokenizerFast(
        tokenizer_object=Tokenizer(WordLevel(vocabulary, unk_token="token0")),
        unk_token="token0",
        bos_token="token1",
        eos_token="token2",
        chat_template="{{ messages[0]['content'] }}",
    )
    tokenizer.save_pretrained(directory)
    return directory


def run_converter(source: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--output", str(output)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_conversion_preserves_long_context_and_bf16_hybrid_cache(
    source: Path, tmp_path: Path
) -> None:
    output = tmp_path / "converted"
    result = run_converter(source, output)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (output / "config.json").is_file(), result.stdout + result.stderr
    config = json.loads((output / "config.json").read_text())
    assert config["quantization"]["bits"] == 6
    assert config["quantization"]["group_size"] == 64
    assert config["quantization"]["model.layers.0.mlp.gate"]["bits"] == 8
    assert config["max_position_embeddings"] == 131072
    assert config["sliding_window"] == 1024
    assert config["layer_types"] == ["sliding_attention", "full_attention"]
    model, tokenizer = load(str(output))
    assert tokenizer.chat_template == "{{ messages[0]['content'] }}"
    cache = model.make_cache()
    assert isinstance(cache[0], RotatingKVCache)
    assert isinstance(cache[1], KVCache)
    logits = model(mx.array([[3, 4]]), cache=cache)
    mx.eval(logits)
    assert mx.all(mx.isfinite(logits)).item()
    assert all(entry.keys.dtype == mx.bfloat16 for entry in cache)


def test_truncated_checkpoint_is_rejected_before_creating_output(
    source: Path, tmp_path: Path
) -> None:
    shard = source / "model.safetensors"
    with shard.open("r+b") as stream:
        stream.truncate(shard.stat().st_size - 8)
    output = tmp_path / "converted"
    result = run_converter(source, output)
    assert result.returncode != 0
    assert not output.exists()


def test_existing_output_is_preserved(source: Path, tmp_path: Path) -> None:
    output = tmp_path / "converted"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("existing model")
    result = run_converter(source, output)
    assert result.returncode != 0
    assert sentinel.read_text() == "existing model"
