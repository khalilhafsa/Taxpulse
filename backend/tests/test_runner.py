"""Checks the real CrewAI plumbing with the network call to Claude replaced by a canned answer."""
import json

from crewai.llms.providers.anthropic.completion import AnthropicCompletion

from app.agents import runner as runner_module
from app.agents.profiler import SPEC
from app.agents.schemas import ProfileDraft
from tests.conftest import FIXTURES


def test_crewai_runner_returns_validated_profile(monkeypatch):
    answer = (FIXTURES / "nordlicht_profile.json").read_text(encoding="utf-8")
    calls = []

    def fake_call(self, messages, *args, **kwargs):
        calls.append(self.model)
        # Claude 5.5 models reject the temperature parameter with a 400 error.
        assert self.temperature is None and self.top_p is None
        return answer

    monkeypatch.setattr(AnthropicCompletion, "call", fake_call)
    monkeypatch.setattr(runner_module.settings, "anthropic_api_key", "test-key")

    result = runner_module.crewai_runner(spec=SPEC, task="Build the profile.", expected_output="A profile.",
                                         schema=ProfileDraft, model="anthropic/claude-sonnet-5-5")

    assert isinstance(result.output, ProfileDraft)
    assert result.output.company_name == "Nordlicht Immobilien GmbH & Co. KG"
    assert result.model == "claude-sonnet-5-5"
    assert calls and "claude-sonnet-5-5" in calls[0]


def test_parse_fallback_extracts_json_from_text():
    data = json.loads((FIXTURES / "nordlicht_profile.json").read_text(encoding="utf-8"))
    raw = "Here is the profile:\n" + json.dumps(data) + "\nDone."
    assert runner_module._parse(raw, ProfileDraft).keywords[0] == "real estate"
