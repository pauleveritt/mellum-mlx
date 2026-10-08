"""The five ladder rungs: fixture, user sentence, test command, and pass check."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PYTEST = ["uv", "run", "--offline", "pytest", "-q"]
IGNORED = shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", "node_modules")


def copy_fixture(fixture: str, dest: Path) -> Path:
    """Copy a fixture to ``dest`` without any environment or cache directories."""
    shutil.copytree(FIXTURES / fixture, dest, ignore=IGNORED)
    return dest


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


def _tests_pass(cmd: list[str], ws: Path) -> bool:
    return subprocess.run(cmd, cwd=ws, capture_output=True, text=True).returncode == 0


def _collect(ws: Path) -> set[str]:
    out = subprocess.run(
        ["uv", "run", "--offline", "pytest", "--collect-only", "-q"],
        cwd=ws,
        capture_output=True,
        text=True,
    ).stdout
    return {line.strip() for line in out.splitlines() if "::" in line}


def check_calculator(ws: Path, base: Path) -> CheckResult:
    unchanged = _same(ws, base, "calculator.test.js")
    passed = _tests_pass(["node", "--test", "calculator.test.js"], ws)
    return CheckResult(passed and unchanged, unchanged)


def check_ledger(ws: Path, base: Path) -> CheckResult:
    base_ids, ws_ids = _collect(base), _collect(ws)
    kept = base_ids <= ws_ids
    new = any("balance" in i for i in ws_ids - base_ids)
    passed = _tests_pass(PYTEST, ws) and kept and new
    return CheckResult(passed, kept, {"new_tests": sorted(ws_ids - base_ids)})


def check_rename(ws: Path, base: Path) -> CheckResult:
    unchanged = _same(ws, base, "test_report.py")
    leftover = any(
        "fetch_rows" in p.read_text()
        for p in ws.glob("*.py")
        if p.name != "test_report.py"
    )
    both = not _same(ws, base, "rows.py") and not _same(ws, base, "report.py")
    passed = _tests_pass(PYTEST, ws) and unchanged and not leftover and both
    return CheckResult(passed, unchanged, {"leftover": leftover, "both_changed": both})


def check_feature(ws: Path, base: Path) -> CheckResult:
    unchanged = _same(ws, base, "test_export.py")
    changed = sum(not _same(ws, base, n) for n in ("export.py", "totals.py", "render.py"))
    passed = _tests_pass(PYTEST, ws) and unchanged and changed >= 2
    return CheckResult(passed, unchanged, {"source_files_changed": changed})


def check_edge(ws: Path, base: Path) -> CheckResult:
    unchanged = _same(ws, base, "test_export.py")
    decoy = _same(ws, base, "exports_legacy.py")
    passed = _tests_pass(PYTEST, ws) and unchanged and decoy
    return CheckResult(passed, unchanged, {"decoy_untouched": decoy})


RUNGS: dict[int, Rung] = {
    1: Rung(
        1,
        "calculator",
        "the cart total ignores quantity, fix it",
        ["node", "--test", "calculator.test.js"],
        check_calculator,
    ),
    2: Rung(
        2,
        "ledger",
        "add a balance() that sums the entries, with a test",
        PYTEST,
        check_ledger,
    ),
    3: Rung(3, "rename", "rename fetch_rows to load_rows everywhere", PYTEST, check_rename),
    4: Rung(4, "feature", "make the failing test pass", PYTEST, check_feature),
    5: Rung(5, "edge", "the export is missing the totals row", PYTEST, check_edge),
}
