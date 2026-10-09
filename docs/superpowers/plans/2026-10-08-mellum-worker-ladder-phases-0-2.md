# Mellum Worker Ladder, Phases 0–2 (Pi) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the five-rung fixture ladder, a Pi runner, a replayable scorer, the project-local Mellum worker, and run phases 0–2 (baseline profile, tuned profile, conditional guards) on Pi.

**Architecture:** Fixtures are self-contained projects whose own tests are the check. `ladder/run_ladder.py` copies a fixture to scratch, switches the oMLX profile through the admin API (snapshot/restore), launches `pi -p` in the report's clean profile with the bundle's `record-pi.js` capturing every request/tool event, then `ladder/score.py` turns the evidence into a `Score` row. Guards are a child-only Pi extension added in phase 2 for columns that were non-zero.

**Tech Stack:** Python 3.14 stdlib (`argparse`, `json`, `subprocess`, `urllib`), pytest, Pi 1.0.2 (`pi -p`), oMLX 0.6.4 admin API, Node for the JS fixture and the Pi extension.

**Spec:** `docs/superpowers/specs/2026-10-08-mellum-worker-recipe-design.md`

## Global Constraints

- Python `>=3.14`; `uv` manages the repo env; fixtures are self-contained with their own `pyproject.toml` + `uv.lock`.
- Never modify weights, model filenames, or `~/.omlx/model_settings.json` without a timestamped backup; the runner restores the server profile on exit, including on failure.
- Scoring never uses process exit status; `passed` comes from the fixture check.
- The worker tool set is exactly `read, grep, find, ls, bash, edit, write`.
- The worker prompt states facts, not rules of conduct.
- Each fixture file stays under 60 lines; no acceptance file lives in a fixture workspace.
- Gate runs are `--repeat 3`; wall time is recorded and labelled untrusted.
- Pi direct mode is `pi -p --no-extensions --no-skills --no-context-files --no-session --thinking high --tools read,grep,find,ls,bash,edit,write --append-system-prompt prompts/mellum-worker.md -e ladder/record-pi.js`.
- Commits touch only ladder/fixture/prompt/agent/doc files; the pre-existing uncommitted README/main.py/pyproject changes are left alone.

## Review Focus

1. A `bash` call that writes a file through `>`/`>>`/`tee`/heredoc must count as `bash_file_mutations`, even when wrapped in `cd … && …` — pinned in Task 2 `test_bash_mutations_*`.
2. A `write` to a path that did not exist in the baseline is a creation, not a clobber — pinned in Task 2 `test_write_existing_only_counts_baseline_paths`.
3. Rung 2 must accept the model adding tests to the existing test file; byte-compare would wrongly fail it — pinned in Task 1 `test_rung2_check_accepts_added_test`.
4. Profile restore must run when the Pi process times out — pinned in Task 3 `test_restore_runs_on_exception`.
5. An oMLX settings PUT that returns 200 but does not change the live value must be detected — pinned in Task 3 `test_apply_verifies_live_settings`.

---

### Task 1: Fixtures (rungs 1–5) and their self-tests

**Files:**
- Create: `fixtures/calculator/{calculator.js,calculator.test.js,package.json,.gitignore}` (copy of `docs/research/mellum-recovery-2026-10-07/fixtures/coding/`)
- Create: `fixtures/ledger/{pyproject.toml,ledger.py,test_ledger.py,.gitignore}`
- Create: `fixtures/rename/{pyproject.toml,rows.py,report.py,test_report.py,.gitignore}`
- Create: `fixtures/feature/{pyproject.toml,export.py,totals.py,render.py,test_export.py,.gitignore}`
- Create: `fixtures/edge/{pyproject.toml,export.py,totals.py,render.py,exports_legacy.py,test_export.py,.gitignore}`
- Create: `ladder/__init__.py`, `ladder/rungs.py`
- Test: `tests/test_fixtures.py`

**Interfaces:**
- Produces: `ladder.rungs.RUNGS: dict[int, Rung]` where `Rung(number, fixture: str, sentence: str, test_cmd: list[str], check: Callable[[Path, Path], CheckResult])`; `CheckResult(passed: bool, tests_unchanged: bool, details: dict)`. `check(workspace, baseline)` is pure over two directory trees.

- [ ] **Step 1: Write the fixture self-test**

```python
# tests/test_fixtures.py
import shutil, subprocess
from pathlib import Path
import pytest
from ladder.rungs import RUNGS, FIXTURES

def run_tests(rung, cwd):
    return subprocess.run(rung.test_cmd, cwd=cwd, capture_output=True, text=True).returncode

@pytest.mark.parametrize("n", [1, 4, 5])
def test_baseline_fails_before_fix(n, tmp_path):
    rung = RUNGS[n]
    ws = tmp_path / "ws"; shutil.copytree(FIXTURES / rung.fixture, ws)
    assert run_tests(rung, ws) != 0

@pytest.mark.parametrize("n", [2, 3])
def test_baseline_passes_before_change(n, tmp_path):
    rung = RUNGS[n]
    ws = tmp_path / "ws"; shutil.copytree(FIXTURES / rung.fixture, ws)
    assert run_tests(rung, ws) == 0

def test_rung2_check_accepts_added_test(tmp_path):
    rung = RUNGS[2]
    ws = tmp_path / "ws"; shutil.copytree(FIXTURES / rung.fixture, ws)
    (ws / "ledger.py").write_text((ws / "ledger.py").read_text() +
        "\n\ndef balance(entries):\n    return sum(e.amount for e in entries)\n")
    (ws / "test_ledger.py").write_text((ws / "test_ledger.py").read_text() +
        "\n\ndef test_balance():\n    from ledger import Entry, balance\n"
        "    assert balance([Entry('a', 5), Entry('b', -2)]) == 3\n")
    result = rung.check(ws, FIXTURES / rung.fixture)
    assert result.passed and result.tests_unchanged

def test_rung5_decoy_edit_fails(tmp_path):
    rung = RUNGS[5]
    ws = tmp_path / "ws"; shutil.copytree(FIXTURES / rung.fixture, ws)
    (ws / "exports_legacy.py").write_text("# touched\n")
    assert not rung.check(ws, FIXTURES / rung.fixture).passed
```

- [ ] **Step 2: Run it to verify it fails** — `uv run pytest tests/test_fixtures.py -q` → ImportError on `ladder.rungs`.

- [ ] **Step 3: Create the Python fixtures** (each file < 60 lines; `pyproject.toml` per fixture):

```toml
# fixtures/<name>/pyproject.toml
[project]
name = "<name>"
version = "0.0.0"
requires-python = ">=3.14"
dependencies = []
[dependency-groups]
dev = ["pytest>=9.1.1"]
[tool.pytest.ini_options]
testpaths = ["."]
```

`.gitignore` in each: `.venv/`, `__pycache__/`, `.pytest_cache/`.

`fixtures/ledger/ledger.py`:
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Entry:
    memo: str
    amount: int

def entries_from_lines(lines):
    out = []
    for line in lines:
        memo, amount = line.rsplit(",", 1)
        out.append(Entry(memo.strip(), int(amount)))
    return out
```
`fixtures/ledger/test_ledger.py`:
```python
from ledger import Entry, entries_from_lines

def test_parses_lines():
    assert entries_from_lines(["coffee, -3", "pay, 10"]) == [Entry("coffee", -3), Entry("pay", 10)]
```

`fixtures/rename/rows.py`:
```python
def fetch_rows(source):
    return [tuple(line.split("|")) for line in source.splitlines() if line]
```
`fixtures/rename/report.py`:
```python
from rows import fetch_rows

def report(source):
    return "\n".join(" ".join(r) for r in fetch_rows(source))
```
`fixtures/rename/test_report.py`:
```python
from report import report

def test_report_joins_cells():
    assert report("a|b\nc|d") == "a b\nc d"
```

`fixtures/feature/totals.py`:
```python
def column_totals(rows):
    if not rows:
        return []
    return [sum(r[i] for r in rows) for i in range(len(rows[0]))]
```
`fixtures/feature/render.py`:
```python
def render_rows(rows):
    return [",".join(str(v) for v in r) for r in rows]
```
`fixtures/feature/export.py`:
```python
from render import render_rows

def export_csv(rows):
    return "\n".join(render_rows(rows))
```
`fixtures/feature/test_export.py`:
```python
from export import export_csv

def test_export_without_totals():
    assert export_csv([[1, 2], [3, 4]]) == "1,2\n3,4"

def test_export_appends_totals_row():
    assert export_csv([[1, 2], [3, 4]], totals=True) == "1,2\n3,4\n4,6"
```
`fixtures/edge/` is `feature/` plus `exports_legacy.py`:
```python
# Legacy exporter kept for an old integration. Do not change.
def export_csv_legacy(rows):
    return "\r\n".join(";".join(str(v) for v in r) for r in rows)
```

- [ ] **Step 4: Write `ladder/rungs.py`**

```python
from __future__ import annotations
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PYTEST = ["uv", "run", "--offline", "pytest", "-q"]

@dataclass(frozen=True)
class CheckResult:
    passed: bool
    tests_unchanged: bool
    details: dict = field(default_factory=dict)

@dataclass(frozen=True)
class Rung:
    number: int
    fixture: str
    sentence: str
    test_cmd: list[str]
    check: Callable[[Path, Path], CheckResult]

def _same(ws: Path, base: Path, name: str) -> bool:
    return (ws / name).read_bytes() == (base / name).read_bytes()

def _tests_pass(cmd, ws) -> bool:
    return subprocess.run(cmd, cwd=ws, capture_output=True, text=True).returncode == 0

def _collect(ws) -> set[str]:
    out = subprocess.run(["uv", "run", "--offline", "pytest", "--collect-only", "-q"],
                         cwd=ws, capture_output=True, text=True).stdout
    return {l.strip() for l in out.splitlines() if "::" in l}

def check_calculator(ws, base):
    unchanged = _same(ws, base, "calculator.test.js")
    return CheckResult(_tests_pass(["node", "--test", "calculator.test.js"], ws) and unchanged, unchanged)

def check_ledger(ws, base):
    base_ids = _collect(base); ws_ids = _collect(ws)
    kept = base_ids <= ws_ids
    new = any("balance" in i for i in ws_ids - base_ids)
    return CheckResult(_tests_pass(PYTEST, ws) and kept and new, kept,
                       {"new_tests": sorted(ws_ids - base_ids)})

def check_rename(ws, base):
    unchanged = _same(ws, base, "test_report.py")
    leftover = any("fetch_rows" in p.read_text() for p in ws.glob("*.py") if p.name != "test_report.py")
    both = not _same(ws, base, "rows.py") and not _same(ws, base, "report.py")
    return CheckResult(_tests_pass(PYTEST, ws) and unchanged and not leftover and both, unchanged,
                       {"leftover": leftover, "both_changed": both})

def check_feature(ws, base):
    unchanged = _same(ws, base, "test_export.py")
    changed = sum(not _same(ws, base, n) for n in ("export.py", "totals.py", "render.py"))
    return CheckResult(_tests_pass(PYTEST, ws) and unchanged and changed >= 2, unchanged,
                       {"source_files_changed": changed})

def check_edge(ws, base):
    unchanged = _same(ws, base, "test_export.py")
    decoy = _same(ws, base, "exports_legacy.py")
    return CheckResult(_tests_pass(PYTEST, ws) and unchanged and decoy, unchanged, {"decoy_untouched": decoy})

RUNGS = {
    1: Rung(1, "calculator", "the cart total ignores quantity, fix it", ["node", "--test", "calculator.test.js"], check_calculator),
    2: Rung(2, "ledger", "add a balance() that sums the entries, with a test", PYTEST, check_ledger),
    3: Rung(3, "rename", "rename fetch_rows to load_rows everywhere", PYTEST, check_rename),
    4: Rung(4, "feature", "make the failing test pass", PYTEST, check_feature),
    5: Rung(5, "edge", "the export is missing the totals row", PYTEST, check_edge),
}
```

- [ ] **Step 5: Lock each Python fixture once** — `cd fixtures/<name> && uv lock && uv sync --offline || uv sync` (first sync warms the cache), commit `uv.lock`.

- [ ] **Step 6: Run `uv run pytest tests/test_fixtures.py -q`** → all pass.

- [ ] **Step 7: Commit** — `git add fixtures ladder/__init__.py ladder/rungs.py tests/test_fixtures.py && git commit -m "ladder: five-rung fixtures and checks"`.

---

### Task 2: Scorer

**Files:**
- Create: `ladder/score.py`, `tests/fixtures_score/{pass.jsonl,clobber.jsonl,loop.jsonl,heredoc.jsonl}`
- Test: `tests/test_score.py`

**Interfaces:**
- Consumes: record-pi.js JSONL events `{"type":"provider_request","payload":{...}}`, `{"type":"tool_call","toolName","input"}`, `{"type":"tool_result","toolName","isError","content"}`.
- Produces: `score(events: list[dict], baseline_paths: set[str], baseline_lines: dict[str,int]) -> Score` with fields `tool_calls_by_name: dict[str,int]`, `tool_errors: int`, `edit_anchor_failures: int`, `noop_edits: int`, `write_existing: list[dict]`, `bash_file_mutations: int`, `max_identical_streak: int`, `largest_prompt_chars: int`, `requests: int`; `call_key(name, input) -> str`; `bash_mutates(command) -> bool`; `Score.as_row() -> dict`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_score.py
import json
from pathlib import Path
from ladder.score import score, call_key, bash_mutates

EV = Path(__file__).parent / "fixtures_score"
def load(name): return [json.loads(l) for l in (EV / name).read_text().splitlines() if l]

def test_pass_run_counts_tools():
    s = score(load("pass.jsonl"), {"calculator.js"}, {"calculator.js": 3})
    assert s.tool_calls_by_name == {"read": 1, "edit": 1, "bash": 1}
    assert s.tool_errors == 0 and s.write_existing == [] and s.max_identical_streak == 1

def test_write_existing_only_counts_baseline_paths():
    s = score(load("clobber.jsonl"), {"export.py"}, {"export.py": 40})
    assert s.write_existing == [{"path": "export.py", "lines_before": 40, "lines_after": 2}]
    s2 = score(load("clobber.jsonl"), set(), {})
    assert s2.write_existing == []

def test_identical_streak_counts_successful_repeats():
    assert score(load("loop.jsonl"), set(), {}).max_identical_streak == 6

def test_anchor_failures_and_noop_edits():
    s = score(load("loop.jsonl"), set(), {})
    assert s.edit_anchor_failures == 2 and s.noop_edits == 1

def test_bash_mutations_heredoc_and_redirect():
    assert bash_mutates("cat > a.py <<'EOF'\nx\nEOF")
    assert bash_mutates("cd src && echo hi >> log.txt")
    assert bash_mutates("printf 'x' | tee out.py")
    assert not bash_mutates("uv run pytest -q 2>&1")
    assert not bash_mutates("grep -rn fetch_rows . ")
    assert score(load("heredoc.jsonl"), set(), {}).bash_file_mutations == 1

def test_call_key_is_order_insensitive():
    assert call_key("edit", {"a": 1, "b": 2}) == call_key("edit", {"b": 2, "a": 1})
```

Evidence files (one JSON object per line). `pass.jsonl`: one `provider_request` with `payload.messages[0].content` of 100 chars, `tool_call read {"path":"calculator.js"}`, `tool_result read isError false`, `tool_call edit {...}`, `tool_result edit "Edit applied"`, `tool_call bash {"command":"node --test calculator.test.js"}`, `tool_result bash`. `clobber.jsonl`: `tool_call write {"path":"export.py","content":"x\ny\n"}` + result. `loop.jsonl`: six identical `tool_call read {"path":"app.py"}` each with a non-error result, two `tool_call edit` with results `isError true, content "oldString not found"`, one `edit` with result `"No changes made"`. `heredoc.jsonl`: `tool_call bash {"command":"cat > new.py <<'EOF'\nprint(1)\nEOF"}` + result.

- [ ] **Step 2: Run** `uv run pytest tests/test_score.py -q` → ImportError.

- [ ] **Step 3: Implement `ladder/score.py`**

```python
from __future__ import annotations
import json, re
from dataclasses import dataclass, field, asdict

_REDIRECT = re.compile(r"(?<![<>&\d])>{1,2}\s*(?!&)\S|\btee\b|<<-?\s*['\"]?\w")

def bash_mutates(command: str) -> bool:
    cleaned = re.sub(r"2>&1|2>/dev/null|>/dev/null|&>/dev/null", "", command)
    return bool(_REDIRECT.search(cleaned))

def call_key(name: str, payload) -> str:
    return name + "\0" + json.dumps(payload, sort_keys=True, default=str)

@dataclass
class Score:
    requests: int = 0
    largest_prompt_chars: int = 0
    tool_calls_by_name: dict = field(default_factory=dict)
    tool_errors: int = 0
    edit_anchor_failures: int = 0
    noop_edits: int = 0
    write_existing: list = field(default_factory=list)
    bash_file_mutations: int = 0
    max_identical_streak: int = 0
    def as_row(self) -> dict:
        d = asdict(self); d["write_existing"] = len(self.write_existing); return d

def _path(inp) -> str | None:
    for k in ("path", "filePath", "file_path"):
        if isinstance(inp, dict) and k in inp: return str(inp[k])
    return None

def score(events, baseline_paths, baseline_lines) -> Score:
    s = Score(); streak = 0; last = None; pending = []
    for ev in events:
        t = ev.get("type")
        if t == "provider_request":
            s.requests += 1
            s.largest_prompt_chars = max(s.largest_prompt_chars, len(json.dumps(ev.get("payload", {}))))
        elif t == "tool_call":
            name, inp = ev["toolName"], ev.get("input", {})
            s.tool_calls_by_name[name] = s.tool_calls_by_name.get(name, 0) + 1
            key = call_key(name, inp)
            streak = streak + 1 if key == last else 1
            last = key; s.max_identical_streak = max(s.max_identical_streak, streak)
            pending.append((name, inp))
            if name == "write":
                p = _path(inp)
                if p and p in baseline_paths:
                    s.write_existing.append({"path": p, "lines_before": baseline_lines.get(p, 0),
                                             "lines_after": str(inp.get("content", "")).count("\n") + 1})
            if name == "bash" and bash_mutates(str(inp.get("command", ""))):
                s.bash_file_mutations += 1
        elif t == "tool_result":
            name = ev["toolName"]; content = str(ev.get("content", ""))
            if ev.get("isError"): s.tool_errors += 1
            if name == "edit":
                if "not found" in content or "oldString" in content: s.edit_anchor_failures += 1
                if "No changes made" in content: s.noop_edits += 1
    return s
```

- [ ] **Step 4: Run tests** → pass. Adjust `_REDIRECT` until the five `bash_mutates` cases pass; keep the test as the spec.

- [ ] **Step 5: Commit** — `git add ladder/score.py tests/test_score.py tests/fixtures_score && git commit -m "ladder: replayable scorer over record-pi events"`.

---

### Task 3: oMLX profile client

**Files:**
- Create: `ladder/omlx_profiles.py`
- Test: `tests/test_omlx_profiles.py`

**Interfaces:**
- Produces: `PROFILES: dict[str, dict]` (`baseline`, `tuned` as in spec 5.1); `class AdminClient(base_url)` with `get_settings(model_id) -> dict`, `put_settings(model_id, patch) -> dict`; `apply_profile(client, model_id, name) -> dict` (PUTs then GETs and raises `ProfileMismatch` if any key differs); `@contextmanager profile(client, model_id, name, settings_path)` which backs up `settings_path` to `settings_path + ".bak-ladder-<ts>"`, applies, yields, and restores the original settings via PUT of the snapshot's values in `finally`.

- [ ] **Step 1: Failing tests with a fake client**

```python
# tests/test_omlx_profiles.py
import json, pytest
from ladder.omlx_profiles import PROFILES, apply_profile, profile, ProfileMismatch

class Fake:
    def __init__(self, live, honest=True): self.live, self.honest, self.puts = dict(live), honest, []
    def get_settings(self, model_id): return dict(self.live)
    def put_settings(self, model_id, patch):
        self.puts.append(patch)
        if self.honest: self.live.update(patch)
        return {"success": True}

def test_apply_verifies_live_settings():
    with pytest.raises(ProfileMismatch):
        apply_profile(Fake({"max_tokens": 4096}, honest=False), "m", "tuned")

def test_restore_runs_on_exception(tmp_path):
    p = tmp_path / "model_settings.json"; p.write_text(json.dumps({"models": {"m": {"max_tokens": 4096}}}))
    fake = Fake({"max_tokens": 4096, "thinking_budget_enabled": False})
    with pytest.raises(RuntimeError):
        with profile(fake, "m", "tuned", p): raise RuntimeError("pi timed out")
    assert fake.live["max_tokens"] == 4096 and fake.live["thinking_budget_enabled"] is False
    assert any(f.name.startswith("model_settings.json.bak-ladder-") for f in tmp_path.iterdir())

def test_profiles_have_required_keys():
    for name in ("baseline", "tuned"):
        assert {"max_tokens", "thinking_budget_enabled", "presence_penalty"} <= PROFILES[name].keys()
```

- [ ] **Step 2: Run → fails.** **Step 3: Implement**

```python
# ladder/omlx_profiles.py
from __future__ import annotations
import json, shutil, time, urllib.request
from contextlib import contextmanager
from pathlib import Path

PROFILES = {
    "baseline": {"max_context_window": 56000, "max_tokens": 4096, "thinking_budget_enabled": False,
                 "thinking_budget_tokens": None, "presence_penalty": 0.0, "repetition_penalty": 1.0,
                 "max_tool_result_tokens": None, "chat_template_kwargs": None, "forced_ct_kwargs": None},
    "tuned": {"max_context_window": 56000, "max_tokens": 16384, "thinking_budget_enabled": True,
              "thinking_budget_tokens": 4096, "presence_penalty": 0.5, "repetition_penalty": 1.0,
              "max_tool_result_tokens": 4000, "chat_template_kwargs": {"enable_thinking": True},
              "forced_ct_kwargs": ["enable_thinking"]},
}

class ProfileMismatch(RuntimeError): ...

class AdminClient:
    def __init__(self, base_url="http://127.0.0.1:8001"): self.base = base_url.rstrip("/")
    def _json(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read() or b"{}")
    def get_settings(self, model_id):
        for m in self._json("GET", "/admin/api/models").get("models", []):
            if m.get("id") == model_id: return m["settings"]
        raise KeyError(model_id)
    def put_settings(self, model_id, patch):
        return self._json("PUT", f"/admin/api/models/{model_id}/settings", patch)

def apply_profile(client, model_id, name):
    patch = PROFILES[name]; client.put_settings(model_id, patch)
    live = client.get_settings(model_id)
    bad = {k: (v, live.get(k)) for k, v in patch.items() if live.get(k) != v}
    if bad: raise ProfileMismatch(f"{name}: {bad}")
    return live

@contextmanager
def profile(client, model_id, name, settings_path: Path):
    settings_path = Path(settings_path)
    snapshot = client.get_settings(model_id)
    if settings_path.exists():
        shutil.copy2(settings_path, settings_path.with_name(settings_path.name + f".bak-ladder-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"))
    try:
        yield apply_profile(client, model_id, name)
    finally:
        client.put_settings(model_id, {k: snapshot.get(k) for k in PROFILES[name]})
```

- [ ] **Step 4: Run tests → pass. Step 5: Commit** `git add ladder/omlx_profiles.py tests/test_omlx_profiles.py && git commit -m "ladder: oMLX profile switch with snapshot and verified restore"`.

---

### Task 4: Worker prompt v2, Pi agent file, record extension, runner (direct mode)

**Files:**
- Create: `prompts/mellum-worker.md`, `.pi/agents/mellum-worker.md`, `ladder/record-pi.js`, `ladder/run_ladder.py`
- Test: `tests/test_runner.py` (argument building and run-record shape only; no live model)

**Interfaces:**
- Consumes: `RUNGS`, `score`, `profile`, `AdminClient`.
- Produces: CLI `uv run python -m ladder.run_ladder --harness pi --mode direct --profile baseline --rung 1 --repeat 1 --out docs/research/ladder/<phase>`; per run `run.json` (`rung, repeat, profile, mode, harness, prompt_version, versions{pi,omlx,model_settings}, sentence, started, wall_seconds, deadline_hit, check{passed,tests_unchanged,details}, score{...}, diff_stat, files_created`) and an appended `table.md` row; `build_pi_direct_args(prompt_file, record_file, sentence) -> list[str]`.

- [ ] **Step 1: Write `prompts/mellum-worker.md`** (version header `<!-- mellum-worker prompt v2 -->`):

```
You edit code in this repository to complete one task.

Tools, stated exactly:
- grep finds a literal string in files and prints file, line number, and the line.
- find and ls list files; read shows a file, or a line range of a file.
- edit replaces one exact existing region of a file with new text. The old text must match the file byte for byte.
- write creates a new file. On an existing file it replaces the entire content, so the content must be the whole file.
- bash runs one command in the working directory.

The test command:
- A pyproject.toml with pytest in it means the command is: uv run --offline pytest -q
- A package.json with a test file means the command is: node --test
- A command named in the task is the command.

Procedure:
1. Restate the task in one line.
2. Find the files: grep for the identifiers named in the task. If none are named, grep for the words in the task that look like code.
3. Read the matching regions, and the test that covers them.
4. Make the smallest change that completes the task.
5. Run the test command.
6. Reply with: the files changed, the test output pasted verbatim, and anything not done.

If the files for the task cannot be found, reply with what is missing and stop.
```

- [ ] **Step 2: Write `.pi/agents/mellum-worker.md`** — the frontmatter from spec 5.3 followed by the prompt body (the runner reads the body from `prompts/mellum-worker.md`; the agent file duplicates it so Pi delegated mode works without the runner; a test asserts the two bodies match).

- [ ] **Step 3: Copy the bundle's `record-pi.js` to `ladder/record-pi.js`** and delete the `MELLUM_MAX_REQUESTS` abort lines (the deadline bounds the run). Keep `MELLUM_TRACE_FILE`.

- [ ] **Step 4: Failing runner tests**

```python
# tests/test_runner.py
from pathlib import Path
from ladder.run_ladder import build_pi_direct_args, PROMPT_FILE

def test_direct_args_are_the_clean_profile():
    args = build_pi_direct_args(Path("/tmp/trace.jsonl"), "fix it")
    for flag in ("-p", "--no-extensions", "--no-skills", "--no-context-files", "--no-session"):
        assert flag in args
    assert args[args.index("--tools") + 1] == "read,grep,find,ls,bash,edit,write"
    assert args[args.index("--append-system-prompt") + 1] == str(PROMPT_FILE)
    assert args[-1] == "fix it"

def test_agent_file_body_matches_prompt():
    body = Path(".pi/agents/mellum-worker.md").read_text().split("---", 2)[2].strip()
    assert body == PROMPT_FILE.read_text().strip()
```

- [ ] **Step 5: Implement `ladder/run_ladder.py`**

```python
from __future__ import annotations
import argparse, json, os, shutil, subprocess, tempfile, time
from pathlib import Path
from .omlx_profiles import AdminClient, profile
from .rungs import FIXTURES, RUNGS
from .score import score

ROOT = Path(__file__).resolve().parent.parent
PROMPT_FILE = ROOT / "prompts" / "mellum-worker.md"
RECORD_EXT = ROOT / "ladder" / "record-pi.js"
MODEL = "omlx/Mellum2.1-12B-A2.5B-Thinking-6bit"
MODEL_ID = MODEL.split("/", 1)[1]
TOOLS = "read,grep,find,ls,bash,edit,write"

def build_pi_direct_args(trace: Path, sentence: str) -> list[str]:
    return ["pi", "-p", "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes",
            "--no-context-files", "--no-session", "--thinking", "high", "--model", MODEL,
            "--tools", TOOLS, "--append-system-prompt", str(PROMPT_FILE), "-e", str(RECORD_EXT), sentence]

def git(ws, *a): return subprocess.run(["git", *a], cwd=ws, capture_output=True, text=True).stdout

def prepare_workspace(rung, scratch: Path) -> Path:
    ws = scratch / f"rung{rung.number}"; shutil.copytree(FIXTURES / rung.fixture, ws)
    git(ws, "init", "-q"); git(ws, "add", "-A"); git(ws, "-c", "user.name=ladder", "-c", "user.email=l@l", "commit", "-qm", "baseline")
    if (ws / "pyproject.toml").exists(): subprocess.run(["uv", "sync", "--offline"], cwd=ws, capture_output=True)
    return ws

def baseline_index(ws: Path):
    paths = {p for p in git(ws, "ls-files").split() if p}
    return paths, {p: (ws / p).read_text(errors="replace").count("\n") + 1 for p in paths}

def run_once(rung, mode, prof, repeat, out: Path, deadline: int, versions: dict) -> dict:
    scratch = Path(tempfile.mkdtemp(prefix="ladder-")); ws = prepare_workspace(rung, scratch)
    paths, lines = baseline_index(ws)
    trace = scratch / "trace.jsonl"; env = {**os.environ, "MELLUM_TRACE_FILE": str(trace), "PI_OFFLINE": "1"}
    args = build_pi_direct_args(trace, rung.sentence)
    started = time.time(); deadline_hit = False
    try:
        proc = subprocess.run(args, cwd=ws, env=env, capture_output=True, text=True, timeout=deadline)
        stdout = proc.stdout
    except subprocess.TimeoutExpired as e:
        deadline_hit = True; stdout = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
    wall = time.time() - started
    events = [json.loads(l) for l in trace.read_text().splitlines() if l.strip()] if trace.exists() else []
    git(ws, "add", "-A")
    rec = {"rung": rung.number, "repeat": repeat, "profile": prof, "mode": mode, "harness": "pi",
           "prompt_version": "v2", "versions": versions, "sentence": rung.sentence, "started": started,
           "wall_seconds_untrusted": round(wall, 1), "deadline_hit": deadline_hit,
           "check": rung.check(ws, FIXTURES / rung.fixture).__dict__,
           "score": score(events, paths, lines).as_row(),
           "diff_stat": git(ws, "diff", "--cached", "--stat"),
           "files_created": [p for p in git(ws, "diff", "--cached", "--name-only", "--diff-filter=A").split() if p],
           "workspace": str(ws)}
    run_dir = out / f"rung{rung.number}-{prof}-{mode}-r{repeat}"; run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(json.dumps(rec, indent=2, default=str))
    if trace.exists(): shutil.copy(trace, run_dir / "trace.jsonl")
    (run_dir / "stdout.txt").write_text(stdout)
    return rec

def table_row(rec) -> str:
    s, c = rec["score"], rec["check"]
    return (f"| {rec['rung']} | {rec['profile']} | {rec['mode']} | {rec['repeat']} | {'pass' if c['passed'] else 'FAIL'} | "
            f"{c['tests_unchanged']} | {s['requests']} | {s['tool_errors']} | {s['edit_anchor_failures']} | {s['noop_edits']} | "
            f"{s['write_existing']} | {s['bash_file_mutations']} | {s['max_identical_streak']} | {s['largest_prompt_chars']} | "
            f"{rec['deadline_hit']} | {rec['wall_seconds_untrusted']} |\n")

HEADER = ("| rung | profile | mode | rep | result | tests_unchanged | requests | tool_errors | anchor_fail | noop_edit | "
          "write_existing | bash_mut | max_streak | largest_prompt_chars | deadline | wall_s (untrusted) |\n"
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness", choices=["pi"], default="pi"); ap.add_argument("--mode", choices=["direct"], default="direct")
    ap.add_argument("--profile", choices=["baseline", "tuned"], required=True)
    ap.add_argument("--rung", type=int, action="append", required=True); ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--deadline", type=int, default=600); ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--omlx", default="http://127.0.0.1:8001")
    a = ap.parse_args(argv)
    client = AdminClient(a.omlx)
    versions = {"pi": subprocess.run(["pi", "--version"], capture_output=True, text=True).stdout.strip(), "omlx": "0.6.4"}
    table = a.out / "table.md"; a.out.mkdir(parents=True, exist_ok=True)
    if not table.exists(): table.write_text(HEADER)
    with profile(client, MODEL_ID, a.profile, Path.home() / ".omlx" / "model_settings.json") as live:
        versions["model_settings"] = {k: live.get(k) for k in ("max_tokens", "thinking_budget_tokens", "presence_penalty")}
        for n in a.rung:
            for r in range(1, a.repeat + 1):
                rec = run_once(RUNGS[n], a.mode, a.profile, r, a.out, a.deadline, versions)
                with table.open("a") as f: f.write(table_row(rec))
                print(table_row(rec), end="")

if __name__ == "__main__": main()
```

- [ ] **Step 6: Run tests → pass. Step 7: Smoke** `uv run python -m ladder.run_ladder --profile baseline --rung 1 --repeat 1 --out /tmp/ladder-smoke` → one row; inspect `trace.jsonl` has `provider_request` events and the system prompt contains "mellum-worker prompt v2".

- [ ] **Step 8: Commit** `git add prompts .pi/agents ladder/record-pi.js ladder/run_ladder.py tests/test_runner.py && git commit -m "ladder: Pi direct-mode runner, worker prompt v2, project agent"`.

---

### Task 5: Harness limit fix (Pi models.json)

**Files:** Modify `~/.pi/agent/models.json` (operator file; backup first)

- [ ] **Step 1:** `cp ~/.pi/agent/models.json ~/.pi/agent/models.json.bak-ladder-$(date -u +%Y%m%dT%H%M%SZ)`
- [ ] **Step 2:** set the omlx Mellum entry `contextWindow` to `56000` with `jq`; verify with `jq '.providers.omlx.models[] | select(.id|test("Mellum")) | .contextWindow'` → 56000. Not committed (outside repo); recorded in the phase-0 README.

---

### Task 6: Phase 0 run (baseline) and record

- [ ] **Step 1:** `uv run python -m ladder.run_ladder --profile baseline --rung 1 --rung 2 --rung 3 --rung 4 --rung 5 --repeat 3 --out docs/research/ladder/phase0-baseline`
- [ ] **Step 2:** Write `docs/research/ladder/phase0-baseline/README.md`: the table, pass counts per rung, every non-zero pathology column named, versions, the exact command. Facts only.
- [ ] **Step 3:** Commit `docs/research/ladder/phase0-baseline` (table, READMEs, `run.json`s and traces; omit `stdout.txt` if larger than 200 KB).

---

### Task 7: Phase 1 run (tuned) and comparison

- [ ] **Step 1:** Before the full run, verify the clamp question: with the tuned profile live, send one chat request with `max_tokens: 20000` via `curl` and confirm the response is 200 (clamped) not 4xx. Record the outcome in the phase-1 README. If 4xx, set Pi `maxTokens` to 16384 (already) and note that the server is the cap.
- [ ] **Step 2:** `uv run python -m ladder.run_ladder --profile tuned --rung 1 --rung 2 --rung 3 --rung 4 --rung 5 --repeat 3 --out docs/research/ladder/phase1-tuned`
- [ ] **Step 3:** `docs/research/ladder/phase1-tuned/README.md` with a per-rung baseline-vs-tuned comparison table (pass count, mean requests, max streak, anchor failures, write_existing, bash_mut, deadline hits, largest prompt) and the gate check `largest_prompt_chars` < 200,000 (≈50k tokens).
- [ ] **Step 4:** Commit.

---

### Task 8: Phase 2 guards (conditional) and run

**Files:** Create `.pi/extensions/mellum-guards.ts`, `.pi/extensions/mellum-guards.test.mjs`; Modify `.pi/agents/mellum-worker.md` (`subagentOnlyExtensions: ./.pi/extensions/mellum-guards.ts`), `ladder/run_ladder.py` (`--guards` flag adds `-e .pi/extensions/mellum-guards.ts`).

Decision rule from phase 0–1 tables: enable `newFileOnlyWrite` iff any `write_existing` > 0; `loopBreaker` iff any `max_identical_streak` ≥ 5; `stepBudget` iff any `deadline_hit`. If none trips, write the guard file with all three present and `ENABLED = {}` empty, record "not needed" in `docs/research/ladder/phase2-guards/README.md`, and skip the run.

- [ ] **Step 1: Failing Node tests** (`node --test .pi/extensions/mellum-guards.test.mjs`)

```js
import test from "node:test"; import assert from "node:assert/strict";
import { newFileOnlyWrite, createLoopBreaker, createStepBudget } from "./mellum-guards.ts";
test("write to existing path is blocked with the fact", () => {
  const g = newFileOnlyWrite(p => p === "a.py");
  assert.equal(g({ toolName: "write", input: { path: "b.py" } }), undefined);
  assert.match(g({ toolName: "write", input: { path: "a.py" } }).reason, /replaces the entire file/);
});
test("loop breaker trips on the 6th identical call, success or not", () => {
  const g = createLoopBreaker(20, 5); const call = { toolName: "read", input: { path: "x" } };
  for (let i = 0; i < 5; i++) assert.equal(g(call), undefined);
  assert.ok(g(call).block);
});
test("step budget blocks after N calls", () => {
  const g = createStepBudget(2); const c = { toolName: "ls", input: {} };
  assert.equal(g(c), undefined); assert.equal(g(c), undefined); assert.ok(g(c).block);
});
```

- [ ] **Step 2: Implement** — port `createLoopBreaker`/`callKey` from `../local-ai-pi/extensions/guards/loop-breaker.ts` unchanged; add:

```ts
export const newFileOnlyWrite = (exists: (p: string) => boolean) => (call) =>
  call.toolName === "write" && exists(call.input?.path)
    ? { block: true, reason: `${call.input.path} exists; write replaces the entire file. Use edit for an existing file.` }
    : undefined;
export const createStepBudget = (max: number) => { let n = 0; return (call) =>
  ++n > max ? { block: true, reason: `Tool-call budget of ${max} reached. Summarise what was done and stop.` } : undefined; };
export default function (pi) {
  const guards = []; // filled from ENABLED
  pi.on("tool_call", (event) => { for (const g of guards) { const d = g({ toolName: event.toolName, input: event.input }); if (d?.block) return d; } });
}
```
with `ENABLED` set per the decision rule and `exists` backed by `fs.existsSync` resolved against `process.cwd()`.

- [ ] **Step 3:** tests pass; `uv run python -m ladder.run_ladder --profile tuned --guards --rung … --repeat 3 --out docs/research/ladder/phase2-guards`; README with guarded columns before/after; commit.

---

## Self-review notes

- Spec coverage: 5.1 → Task 3/7; 5.2 → Task 5 (Pi) and the already-applied OpenCode limit; 5.3 → Task 4; 5.4 → Task 1; 5.5 (direct) → Task 4; 5.5 delegated and 5.7's OpenCode port are phases 3–4, out of this plan; 5.6 → Task 2; 5.7 → Task 8; phases 0–2 → Tasks 6–8.
- Names used across tasks: `RUNGS`, `FIXTURES`, `CheckResult`, `score`, `Score.as_row`, `call_key`, `bash_mutates`, `PROFILES`, `AdminClient`, `apply_profile`, `profile`, `ProfileMismatch`, `build_pi_direct_args`, `PROMPT_FILE` — consistent.
- Review Focus 1–5 are pinned in Tasks 2, 2, 1, 3, 3 respectively.
