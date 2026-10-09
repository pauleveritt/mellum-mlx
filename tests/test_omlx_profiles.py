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


def test_nopenalty_variant_differs_from_tuned_only_by_penalty():
    tuned, variant = PROFILES["tuned"], PROFILES["tuned-nopenalty"]
    assert variant["presence_penalty"] == 0.0
    assert {k: v for k, v in variant.items() if k != "presence_penalty"} == {k: v for k, v in tuned.items() if k != "presence_penalty"}


def test_profiles_have_required_keys():
    for name in ("baseline", "tuned", "tuned-nopenalty"):
        assert {"max_tokens", "thinking_budget_enabled", "presence_penalty"} <= PROFILES[name].keys()


def test_restore_is_verified_and_names_the_backup(tmp_path):
    from ladder.omlx_profiles import RestoreFailed

    path = tmp_path / "model_settings.json"
    path.write_text("{}")

    class StickyAfterApply(Fake):
        def put_settings(self, model_id, patch):
            self.puts.append(patch)
            if len(self.puts) == 1:
                self.live.update(patch)  # apply lands, restore is silently ignored
            return {"success": True}

    fake = StickyAfterApply({"max_tokens": 4096, "thinking_budget_enabled": False, "presence_penalty": 0.0})
    with pytest.raises(RestoreFailed) as info:
        with profile(fake, "m", "tuned", path):
            pass
    assert ".bak-ladder-" in str(info.value)


def test_restore_failure_chains_the_original_error(tmp_path):
    from ladder.omlx_profiles import RestoreFailed

    class Dies(Fake):
        def put_settings(self, model_id, patch):
            if self.puts:
                raise ConnectionError("server down")
            self.puts.append(patch)
            self.live.update(patch)
            return {}

    with pytest.raises(RestoreFailed) as info:
        with profile(Dies({"max_tokens": 4096, "thinking_budget_enabled": False, "presence_penalty": 0.0}), "m", "tuned", tmp_path / "s.json"):
            raise RuntimeError("pi timed out")
    chain, error = [], info.value
    while error is not None:
        chain.append(type(error))
        error = error.__cause__ or error.__context__
    assert RuntimeError in chain, chain
