from pathlib import Path

from ladder.run_ladder import PROMPT_FILE, build_pi_direct_args

ROOT = Path(__file__).resolve().parent.parent


def test_direct_args_are_the_clean_profile():
    args = build_pi_direct_args(Path("/tmp/trace.jsonl"), "fix it")
    for flag in ("-p", "--no-extensions", "--no-skills", "--no-context-files", "--no-session"):
        assert flag in args
    assert args[args.index("--tools") + 1] == "read,grep,find,ls,bash,edit,write"
    assert args[args.index("--append-system-prompt") + 1] == str(PROMPT_FILE)
    assert args[-1] == "fix it"


def test_agent_file_body_matches_prompt():
    body = (ROOT / ".pi/agents/mellum-worker.md").read_text().split("---", 2)[2].strip()
    assert body == PROMPT_FILE.read_text().strip()
