import json

import pytest

from ladder.omlx_profiles import PROFILES, ProfileMismatch, apply_profile, profile


class Fake:
    def __init__(self, live, honest=True):
        self.live = dict(live)
        self.honest = honest
        self.puts = []

    def get_settings(self, model_id):
        return dict(self.live)

    def put_settings(self, model_id, patch):
        self.puts.append(patch)
        if self.honest:
            self.live.update(patch)
        return {"success": True}


def test_apply_verifies_live_settings():
    with pytest.raises(ProfileMismatch):
        apply_profile(Fake({"max_tokens": 4096}, honest=False), "m", "tuned")


def test_restore_runs_on_exception(tmp_path):
    path = tmp_path / "model_settings.json"
    path.write_text(json.dumps({"models": {"m": {"max_tokens": 4096}}}))
    fake = Fake({"max_tokens": 4096, "thinking_budget_enabled": False})
    with pytest.raises(RuntimeError):
        with profile(fake, "m", "tuned", path):
            raise RuntimeError("pi timed out")
    assert fake.live["max_tokens"] == 4096
    assert fake.live["thinking_budget_enabled"] is False
    assert any(f.name.startswith("model_settings.json.bak-ladder-") for f in tmp_path.iterdir())


def test_profiles_have_required_keys():
    for name in ("baseline", "tuned"):
        assert {"max_tokens", "thinking_budget_enabled", "presence_penalty"} <= PROFILES[name].keys()
