# Package verification, 2026-10-07

## OpenCode follow-up verification

A subsequent exact-prompt “Take a look around” trial was inspected through
SQLite. The first turn completed fixture inspection without a skill invocation;
the second made an irrelevant shell-based website fetch and accepted a false
premise about loading Superpowers. That behavior is recorded as unresolved,
not a passing correctness check. The earlier successful fixture scores below
remain unchanged.

- OpenCode 1.18.35 was driven headlessly. SQLite was read only for ten newly
  created diagnostic sessions, plus a separately executed portable-runner
  session. Database version metadata matches the installed CLI version.
- All three canonical-path file retrievals matched exact one-line goldens:
  nine values, zero tool errors, substantive finals with `stop`.
- The coding fixture completed with zero tool errors; independent tests passed
  3/3 and the original test file was unchanged.
- Configured, `--pure`-only, and clean conversation finals/tools were reviewed.
  The setup-confounded initial run and symlink-path recovery were retained
  separately; they are not scored as paired clean model failures.
- Session cumulative input/output/cache-read counters matched the sums of their
  assistant-message counters for all ten sessions.
- Actual request capture confirmed the clean profile's model, 4,096 output
  cap, sampling parameters, and enabled/preserved thinking template flags.
- The packaged OpenCode runner and read-only SQLite inspector were executed
  successfully. The standalone configuration file also completed a separate
  greeting with correct request settings.
- Both new JavaScript files passed `node --check`. Working IDE analysis
  submitted `run_opencode.mjs`, `inspect_opencode.mjs`, and `opencode-clean.json`;
  it returned `{"items":[]}` with no reported diagnostics. As below, per-file
  coverage was not enumerated, so complete IDE inspection is not asserted.
- Exported evidence was checked for private workstation paths and credential
  markers. No SQLite database, credentials, unrelated messages, or wholesale
  bootstrap was packaged. The diagnostic proxy was stopped; oMLX was preserved.

The manifest and ZIP integrity checks are regenerated after these additions.

## Original Pi/direct-runtime verification

Verified before packaging:

- All twenty direct cases reproduced their token counts and SHA-256 hashes with
  the pinned original tokenizer; expected literals exist in their message data.
- All five new native controls matched recorded input token counts and hashes.
- Packaged direct MLX runner passed the 965-token control. Packaged native runner
  passed the 49,993-token control with equal input tokens.
- Packaged headless Pi retrieval returned its exact golden with no tool errors.
- Packaged Pi coding completed normally; independent Node tests passed 3/3 and
  tests were unchanged. The final patch and independent test log are in evidence.
- Packaged Pi conversation returned substantive answers, read README on the
  summary turn, and used no tool on the challenge turn.
- Both bundled Python scripts compiled. The conversion snapshot matched the
  project's `main.py` byte-for-byte and its offline `--check` verified the pinned
  original source shards; no weights were rewritten.
- Both Pi JavaScript files passed `node --check`.
- Twenty-five local Markdown links in the report, bundle instructions, handoff,
  project README, and docs index resolved. JSON, compressed cases, and Pi fixture
  goldens parsed and matched. Evidence/prompt cases contain no workstation user
  paths or credential markers checked by the packaging validation.

IDE analysis: working analysis, `min_severity=strong_warning`.

Source files submitted: four — `reproduce.py`, `converter_snapshot.py`,
`run_pi.mjs`, `record-pi.js`.

Diagnostics fixed in final packaging pass: none. Earlier dynamic tokenizer
typing diagnostics in the reproducer had already been corrected.

Final IDE result: returned `{"items":[]}`, with no reported diagnostics or
timeout. The response did not enumerate per-file coverage, so this is not a
claim that every file received a complete IDE inspection. Python compilation,
JavaScript syntax checks, and actual runner executions provide separate
verification above.

The first package-integrity check expected Node's TAP-style `# pass 3` marker;
the installed Node reporter emits `ℹ pass 3`. The verifier was corrected to
check the actual pass/fail counters and rerun successfully. This was a verifier
format issue; the independently executed coding tests passed throughout.

Archive integrity is checked separately with `unzip -t`; file hashes are listed
in `manifest.sha256`. This file does not assert a universal model repair, exact
historical-session replay, or physical 16GB-machine validation.
