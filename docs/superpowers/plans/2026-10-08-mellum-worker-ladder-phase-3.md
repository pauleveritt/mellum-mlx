# Mellum Worker Ladder, Phase 3 (Pi delegated mode and the parent-side skill) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure the whole recipe — a normal Pi parent (hosted DeepSeek Flash, Superpowers on) delegating the vague sentence to the Mellum worker through pi-subagents — first as it ships, then with a parent-side `delegate-to-mellum` skill, on all five rungs.

**Architecture:** `ladder/pi_profile.py` mirrors the operator's real `~/.pi/agent` into a temporary agent directory (settings, models, auth, packages symlinked, trust for the scratch workspace) so the parent runs its normal environment without touching it. The scratch workspace carries a copy of `.pi/` whose `mellum-worker.md` has the ladder's recorder appended to `subagentOnlyExtensions`, and, in skill runs, `.pi/skills/delegate-to-mellum/`. The runner's `--mode delegated` launches `pi -p` on the parent, parses the parent's JSON stream for the `subagent` call (the brief) and its final text, and scores the child from the same `record-pi.js` trace as direct mode.

**Tech Stack:** Python 3.14 stdlib, pytest, Pi 1.0.2 + pi-subagents (installed), oMLX 0.6.4 on the baseline profile, DeepSeek Flash through Pi's built-in provider.

**Spec:** `docs/superpowers/specs/2026-10-08-mellum-worker-recipe-design.md` (sections 3, 5.5 delegated, 5.8, 6 phase 3)

## Global Constraints

- The committed `.pi/agents/mellum-worker.md`, `.pi/extensions/mellum-guards.ts`, and the operator's `~/.pi/agent/*` are never modified by the runner; every change lives in the scratch workspace or the temporary agent directory.
- Scoring never uses exit status; `passed` comes from the fixture check, as in phases 0–2.
- The server profile is `baseline` for all phase-3 runs (phase 1 showed no detectable profile effect); guards are on (shipped config, nudge capped at 1).
- Parent runs need the network (DeepSeek); the child env keeps `PI_OFFLINE` unset in delegated mode.
- Gate runs are `--repeat 3`; the parent deadline is 900 s per run; wall time is untrusted.
- Both 3a (no skill) and 3b (skill) run all five rungs so the comparison is paired, rather than only the rungs that failed 3a.
- Commits touch only ladder/fixture/prompt/agent/skill/doc/test files.

## Review Focus

1. A parent that does the task itself instead of delegating must be recorded as `delegated: false`, not scored as a child pass — pinned in Task 2 `test_parse_parent_json_reports_no_delegation`.
2. The scratch agent file must keep the committed guard extension *and* add the recorder — pinned in Task 1 `test_ladder_agent_file_appends_recorder_to_guards`.
3. The mirrored profile must never carry the operator's session history or write back to `~/.pi/agent` — pinned in Task 1 `test_mirror_skips_sessions_and_writes_nothing_to_source`.
4. A skill run and a no-skill run must differ only by the presence of `.pi/skills/delegate-to-mellum` in the workspace — pinned in Task 1 `test_prepare_pi_workspace_skill_toggle`.
5. The parent's brief must be captured verbatim for the record even when the child fails — pinned in Task 2 `test_parse_parent_json_extracts_the_brief`.

---

### Task 1: Temporary Pi profile and the ladder's workspace `.pi/`

**Files:**
- Create: `ladder/pi_profile.py`
- Test: `tests/test_pi_profile.py`

**Interfaces:**
- Produces: `mirror_agent_dir(source: Path, dest: Path, trusted: list[Path]) -> Path` — copies `settings.json`, `models.json`, `auth.json`, `AGENTS.md`, `extensions/` when present; symlinks `git/` and `npm/`; writes `trust.json` as `{str(path): true}` for `trusted`; never copies `sessions/`. `prepare_pi_workspace(ws: Path, record_ext: Path, skill: bool) -> Path` — copies `ROOT/.pi/agents/mellum-worker.md` and `ROOT/.pi/extensions/mellum-guards.ts` into `ws/.pi/`, rewrites the `subagentOnlyExtensions:` line to `./.pi/extensions/mellum-guards.ts, <record_ext absolute>`, and copies `ROOT/.pi/skills/delegate-to-mellum/` only when `skill` is true.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pi_profile.py
import json
from pathlib import Path

from ladder.pi_profile import mirror_agent_dir, prepare_pi_workspace

ROOT = Path(__file__).resolve().parent.parent


def fake_agent_dir(root: Path) -> Path:
    src = root / "agent"
    (src / "git" / "pkg").mkdir(parents=True)
    (src / "npm").mkdir()
    (src / "sessions").mkdir()
    (src / "sessions" / "private.jsonl").write_text("secret")
    (src / "extensions").mkdir()
    for name in ("settings.json", "models.json", "auth.json"):
        (src / name).write_text("{}")
    (src / "AGENTS.md").write_text("notes")
    return src


def test_mirror_skips_sessions_and_writes_nothing_to_source(tmp_path):
    src = fake_agent_dir(tmp_path)
    before = sorted(p.relative_to(src) for p in src.rglob("*"))
    dest = mirror_agent_dir(src, tmp_path / "mirror", [tmp_path / "ws"])
    assert not (dest / "sessions").exists()
    assert (dest / "git").is_symlink() and (dest / "npm").is_symlink()
    assert (dest / "settings.json").read_text() == "{}" and (dest / "AGENTS.md").read_text() == "notes"
    assert json.loads((dest / "trust.json").read_text()) == {str(tmp_path / "ws"): True}
    assert sorted(p.relative_to(src) for p in src.rglob("*")) == before


def test_ladder_agent_file_appends_recorder_to_guards(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    prepare_pi_workspace(ws, Path("/abs/record-pi.js"), skill=False)
    text = (ws / ".pi" / "agents" / "mellum-worker.md").read_text()
    assert "subagentOnlyExtensions: ./.pi/extensions/mellum-guards.ts, /abs/record-pi.js\n" in text
    assert (ws / ".pi" / "extensions" / "mellum-guards.ts").exists()
    committed = (ROOT / ".pi" / "agents" / "mellum-worker.md").read_text()
    assert "record-pi" not in committed


def test_prepare_pi_workspace_skill_toggle(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"; a.mkdir(); b.mkdir()
    prepare_pi_workspace(a, Path("/abs/record-pi.js"), skill=False)
    prepare_pi_workspace(b, Path("/abs/record-pi.js"), skill=True)
    assert not (a / ".pi" / "skills").exists()
    assert (b / ".pi" / "skills" / "delegate-to-mellum" / "SKILL.md").exists()
```

- [ ] **Step 2: Run** `uv run pytest tests/test_pi_profile.py -q` → ImportError.

- [ ] **Step 3: Implement `ladder/pi_profile.py`**

```python
"""A temporary Pi agent directory mirroring the operator's, and the ladder's workspace `.pi/`."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COPIED_FILES = ("settings.json", "models.json", "auth.json", "AGENTS.md")
LINKED_DIRS = ("git", "npm")


def mirror_agent_dir(source: Path, dest: Path, trusted: list[Path]) -> Path:
    """Copy the parent's configuration, link its packages, trust the given workspaces."""
    dest.mkdir(parents=True, exist_ok=True)
    for name in COPIED_FILES:
        if (source / name).exists():
            shutil.copy2(source / name, dest / name)
    if (source / "extensions").is_dir():
        shutil.copytree(source / "extensions", dest / "extensions", dirs_exist_ok=True)
    for name in LINKED_DIRS:
        if (source / name).exists():
            os.symlink(source / name, dest / name, target_is_directory=True)
    (dest / "trust.json").write_text(json.dumps({str(p): True for p in trusted}, indent=2))
    return dest


def prepare_pi_workspace(ws: Path, record_ext: Path, skill: bool) -> Path:
    """Give a scratch workspace the worker definition with the ladder recorder, and optionally the skill."""
    pi = ws / ".pi"
    (pi / "agents").mkdir(parents=True, exist_ok=True)
    (pi / "extensions").mkdir(exist_ok=True)
    shutil.copy2(ROOT / ".pi" / "extensions" / "mellum-guards.ts", pi / "extensions" / "mellum-guards.ts")
    lines = (ROOT / ".pi" / "agents" / "mellum-worker.md").read_text().splitlines(keepends=True)
    rewritten = [
        f"subagentOnlyExtensions: ./.pi/extensions/mellum-guards.ts, {record_ext}\n"
        if line.startswith("subagentOnlyExtensions:") else line
        for line in lines
    ]
    (pi / "agents" / "mellum-worker.md").write_text("".join(rewritten))
    if skill:
        shutil.copytree(ROOT / ".pi" / "skills" / "delegate-to-mellum", pi / "skills" / "delegate-to-mellum")
    return pi
```

- [ ] **Step 4:** The skill directory does not exist yet (Task 5), so `test_prepare_pi_workspace_skill_toggle` needs a placeholder: create `.pi/skills/delegate-to-mellum/SKILL.md` with frontmatter `name: delegate-to-mellum` and a one-line body "Placeholder; replaced in Task 5." Run the file's tests → 3 pass. Commit: `git add ladder/pi_profile.py tests/test_pi_profile.py .pi/skills && git commit -m "ladder: temporary Pi profile mirror and workspace .pi for delegated runs"`.

---

### Task 2: Delegated mode in the runner

**Files:**
- Modify: `ladder/run_ladder.py` (`build_pi_delegated_args`, `parse_parent_json`, `run_once` branching, `--mode delegated`, `--skill`, `HEADER`/`table_row` columns), `ladder/summarize.py` (`not_delegated` flag)
- Test: `tests/test_runner.py`, `tests/test_summarize.py`

**Interfaces:**
- Consumes: `mirror_agent_dir`, `prepare_pi_workspace` from Task 1.
- Produces: `build_pi_delegated_args(sentence) -> list[str]` = `["pi", "-p", "--mode", "json", "--no-session", "--thinking", "high", f"Use mellum-worker to do this: {sentence}"]` (parent model from the mirrored profile's default); `parse_parent_json(stdout) -> dict(delegated: bool, brief: str, parent_final_chars: int, parent_messages: int, subagent_calls: int)`; run.json gains `"parent": {...}` and `"skill": bool`; table gains `deleg` and `brief_chars` columns; summarize flags `not_delegated`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_runner.py (append)
def test_parse_parent_json_extracts_the_brief():
    from ladder.run_ladder import parse_parent_json

    lines = [
        '{"type":"message_end","message":{"role":"assistant","stopReason":"toolUse","content":[{"type":"toolCall","name":"subagent","arguments":{"agent":"mellum-worker","task":"Fix totalCents in calculator.js; run node --test"}}]}}',
        '{"type":"message_end","message":{"role":"assistant","stopReason":"stop","content":[{"type":"text","text":"Done: 3/3 tests pass."}]}}',
    ]
    parent = parse_parent_json("\n".join(lines))
    assert parent["delegated"] is True
    assert parent["brief"] == "Fix totalCents in calculator.js; run node --test"
    assert parent["parent_final_chars"] == len("Done: 3/3 tests pass.")
    assert parent["subagent_calls"] == 1


def test_parse_parent_json_reports_no_delegation():
    from ladder.run_ladder import parse_parent_json

    line = '{"type":"message_end","message":{"role":"assistant","stopReason":"stop","content":[{"type":"toolCall","name":"edit","arguments":{}},{"type":"text","text":"I fixed it myself."}]}}'
    parent = parse_parent_json(line)
    assert parent["delegated"] is False and parent["brief"] == "" and parent["subagent_calls"] == 0


def test_delegated_args_address_the_worker_by_name():
    from ladder.run_ladder import build_pi_delegated_args

    args = build_pi_delegated_args("fix it")
    assert args[:2] == ["pi", "-p"] and "--no-session" in args and "--no-extensions" not in args
    assert args[-1] == "Use mellum-worker to do this: fix it"
```

```python
# tests/test_summarize.py (append)
def test_summarize_flags_runs_where_the_parent_did_not_delegate(tmp_path):
    r = rec(1, True); r["mode"] = "delegated"; r["parent"] = {"delegated": False}
    write_runs(tmp_path, [r, rec(1, True)])
    assert summarize(tmp_path)["nonzero"] == {"not_delegated": 1}
```

- [ ] **Step 2: Run → fail.** **Step 3: Implement** in `ladder/run_ladder.py`:

```python
from .pi_profile import mirror_agent_dir, prepare_pi_workspace

PARENT_PROMPT = "Use mellum-worker to do this: {sentence}"


def build_pi_delegated_args(sentence: str) -> list[str]:
    return ["pi", "-p", "--mode", "json", "--no-session", "--thinking", "high", PARENT_PROMPT.format(sentence=sentence)]


def parse_parent_json(stdout: str) -> dict:
    """What the parent did: whether it launched the worker, the brief it wrote, its final text."""
    brief, final, messages, calls = "", "", 0, 0
    for line in stdout.splitlines():
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        message = event.get("message") or {}
        if event.get("type") != "message_end" or message.get("role") != "assistant":
            continue
        messages += 1
        blocks = [b for b in (message.get("content") or []) if isinstance(b, dict)]
        final = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        for block in blocks:
            if block.get("type") == "toolCall" and block.get("name") == "subagent":
                arguments = block.get("arguments") or {}
                if arguments.get("agent") == "mellum-worker" and arguments.get("task"):
                    calls += 1
                    brief = brief or str(arguments["task"])
    return {"delegated": calls > 0, "brief": brief, "parent_final_chars": len(final.strip()),
            "parent_messages": messages, "subagent_calls": calls}
```

In `run_once`, after `prepare_workspace`: when `mode == "delegated"`, call `prepare_pi_workspace(ws, RECORD_EXT, skill)`, create `agent_dir = mirror_agent_dir(Path.home() / ".pi" / "agent", scratch / "pi-agent", [ws])`, build `env` with `PI_CODING_AGENT_DIR=str(agent_dir)` and **without** `PI_OFFLINE`, use `build_pi_delegated_args(rung.sentence)`, and after the run set `record["parent"] = parse_parent_json(stdout)` and `record["skill"] = skill`. The child's `stop_reason`/`final_text_chars` columns keep their meaning for direct mode; in delegated mode they describe the parent's final message and the record says so (`"final_text_is": "parent"`). Save the brief to `run_dir / "brief.md"`. `main()` gains `--mode direct|delegated`, `--skill` (store_true), and passes `skill` through. `HEADER` and `table_row` append `| deleg | brief_chars |` (empty in direct mode). `summarize` adds `nonzero["not_delegated"]` when `record.get("parent", {}).get("delegated") is False`.

- [ ] **Step 4: Tests green**, then a live smoke: `uv run python -m ladder.run_ladder --mode delegated --profile baseline --guards --rung 1 --repeat 1 --deadline 900 --out /tmp/ladder-delegated-smoke`. Expected: one row, `deleg True`, `brief_chars > 0`, child trace has `provider_request` events whose system prompt contains "mellum-worker prompt v3", and the parent's stdout contains a `subagent` tool call. If the parent never delegates, read its final text before changing anything.

- [ ] **Step 5: Commit** `git add ladder/run_ladder.py ladder/summarize.py tests/test_runner.py tests/test_summarize.py && git commit -m "ladder: delegated mode — mirrored Pi profile, parent brief capture"`.

---

### Task 3: Phase 3a — delegated, no skill

- [ ] **Step 1:** `uv run python -m ladder.run_ladder --mode delegated --profile baseline --guards --rung 1 --rung 2 --rung 3 --rung 4 --rung 5 --repeat 3 --deadline 900 --out docs/research/ladder/phase3a-delegated-noskill`
- [ ] **Step 2:** `docs/research/ladder/phase3a-delegated-noskill/README.md`: pass table against phase 2 (direct); `not_delegated` count; brief lengths; what the parent wrote in its briefs (quote one); whether any parent final was empty or claimed success over a failing child. Facts only.
- [ ] **Step 3:** Commit the record.

---

### Task 4: The `delegate-to-mellum` skill

**Files:** Replace `.pi/skills/delegate-to-mellum/SKILL.md`; Test: `tests/test_skill.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_skill.py
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / ".pi" / "skills" / "delegate-to-mellum" / "SKILL.md"


def test_skill_has_frontmatter_and_the_brief_template():
    text = SKILL.read_text()
    head, body = text.split("---", 2)[1], text.split("---", 2)[2]
    assert "name: delegate-to-mellum" in head and "description:" in head
    for field in ("Files:", "Change:", "Test command:", "Done when:"):
        assert field in body, field
    assert "empty" in body and "re-dispatch" in body
```

- [ ] **Step 2: Write the skill** (replace the placeholder):

```markdown
---
name: delegate-to-mellum
description: Use when handing a coding task to the mellum-worker subagent (a small local model). Scope the task first, send a brief in the fixed template, then verify the result yourself.
---

# Delegate to mellum-worker

mellum-worker is a 12B local model with file tools. It completes bounded
tasks reliably when the brief names the files, the change, and the test
command; it stalls or stops silently on tasks it has to scope itself.

## Before dispatching: scope the task yourself

1. Find the files: `grep -rn <identifier>` or `find` for the names in the
   request. Open them. Name every file the change touches.
2. Name the test command and run it once to see the current failure
   (`uv run pytest -q`, `node --test <file>`, or whatever the project uses).
3. Write the acceptance criterion as the test command exiting 0 plus any
   file that must not change.

## The brief

Send exactly this shape as the `task`:

```
Files: <paths, one per line, relative to the working directory>
Change: <what to change in each file, in one or two sentences each>
Test command: <the exact command, run from <directory>>
Do not change: <files that must stay as they are, or "nothing else">
Done when: the test command exits 0 and you have replied with the files changed and the test output.
```

Do not send the user's sentence as the task. Do not ask the worker to
explore, choose an approach, or decide scope.

## After the worker returns

1. Run the test command yourself. The worker's report is not the result;
   the test exit code is.
2. If the worker's reply is empty, or the tests fail, re-dispatch **once**
   with the same brief plus the failing test output pasted under
   `Current failure:`. A second empty reply means the task is beyond it:
   do the remaining change yourself and say so.
3. Report to the user: files changed, test output, and whether the worker
   or you made the final change.
```

- [ ] **Step 3:** test green; `tests/test_pi_profile.py` still green. Commit `git add .pi/skills tests/test_skill.py && git commit -m "skill: delegate-to-mellum — scope, fixed brief, verify, re-dispatch once"`.

---

### Task 5: Phase 3b — delegated with the skill

- [ ] **Step 1:** `uv run python -m ladder.run_ladder --mode delegated --skill --profile baseline --guards --rung 1 --rung 2 --rung 3 --rung 4 --rung 5 --repeat 3 --deadline 900 --out docs/research/ladder/phase3b-delegated-skill`
- [ ] **Step 2:** `docs/research/ladder/phase3b-delegated-skill/README.md`: paired table 3a vs 3b per rung; `not_delegated`, mean brief length, mean child requests, whether the parent used the template (grep briefs for `Files:`), re-dispatch count (subagent_calls > 1), parent-verified test runs (parent bash calls containing the test command — from the parent stdout). State plainly what the skill bought and cost.
- [ ] **Step 3:** Commit. Then the final whole-branch review as in phases 0–2.

---

## Self-review notes

- Spec coverage: 5.5 delegated → Tasks 1–2; 5.8 skill → Task 4; phase 3 runs → Tasks 3, 5; the empty-final parent-side check (phase-2 record) → the skill's "After the worker returns".
- Names across tasks: `mirror_agent_dir`, `prepare_pi_workspace`, `build_pi_delegated_args`, `parse_parent_json`, `PARENT_PROMPT` — consistent.
- Review Focus 1–5 pinned in Tasks 2, 1, 1, 1, 2.
- Not in this plan: OpenCode delegated mode (phase 4), the README (phase 5).

---

### Task 6 (added after external review): Phase 1 redo with request-level profiles

**Why:** every request in phases 0–2 carried Pi's own `max_tokens 16384`,
`presence_penalty 0`, `temperature 1`, `top_p 0.95`, `top_k 20`, and oMLX gives
request values precedence over the model profile. The phase-1 comparison
therefore never tested the output cap or the penalty, and no run was greedy.

**Files:**
- Modify: `ladder/omlx_profiles.py` (add a `request` block per profile), `ladder/pi_profile.py` (`direct_agent_dir(dest, profile) -> Path` writing a minimal agent dir whose `models.json` omlx entry carries the profile's `samplingParams` and `maxTokens`), `ladder/run_ladder.py` (direct mode uses that agent dir; records `effective_params` in the table and refuses to proceed when the first request's params do not match the profile's `request` block)
- Test: `tests/test_pi_profile.py`, `tests/test_omlx_profiles.py`, `tests/test_runner.py`

**Interfaces:**
- `PROFILES[name]["request"]`: baseline `{"temperature": 0, "top_p": 1, "top_k": 0, "min_p": 0, "seed": 42, "max_tokens": 4096}`; tuned the same with `max_tokens 16384` and `presence_penalty 0.5`; tuned-nopenalty the same as tuned with `presence_penalty 0`. The server-side keys stay as they are.
- The probe in the ledger records which of these keys Pi actually forwards; any key Pi drops is removed from the profile and the record says so.

- [ ] **Step 1:** failing tests — `direct_agent_dir` writes `samplingParams`/`maxTokens` from the profile; the runner raises `ProfileMismatch` when `effective_params` disagree with `PROFILES[name]["request"]` on a key Pi forwards.
- [ ] **Step 2:** implement; `uv run pytest -q` green.
- [ ] **Step 3:** runs, after phase 3b, baseline profile first: `--mode direct --guards --profile baseline|tuned --rung 1..5 --repeat 3 --out docs/research/ladder/phase1c-baseline-greedy` and `phase1d-tuned-effective`.
- [ ] **Step 4:** `docs/research/ladder/phase1d-tuned-effective/README.md`: the paired table, with the effective parameters printed from the records, replacing the phase-1 conclusions.

---

## Backlog (not scheduled)

- **3c — make the skill unconditional, then measure it.** Phase 3b showed the
  parent reads an *available* `delegate-to-mellum` skill in about 1 run in 10.
  Candidates: point the worker's advertised `description` at the skill, or a
  project `AGENTS.md` line. 15 delegated runs; compare brief template use,
  parent self-verification, re-dispatch, and cost against 3a/3b.
- **Nudge guard:** make dormant or add a continuation bound (tool-call budget
  after a nudge) and measure the bounded form; today's cap of 1 is unmeasured.
- **Loop breaker:** the exact replay argues for enabling it (blocks only the
  thrash run); enable and measure.
