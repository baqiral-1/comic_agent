"""Character agent tests."""

from __future__ import annotations

import json

from comic_agent.agents.character_agent.agent import CharacterAgent
from comic_agent.core.models import StoryDocument


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content

    def create(self, **kwargs):  # noqa: ANN003, ANN201
        _ = kwargs
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = _FakeChat(content)


def _story(text: str) -> StoryDocument:
    return StoryDocument(source_path="story.txt", raw_text=text, normalized_text=text)


def test_character_agent_uses_llm_output_when_available(monkeypatch) -> None:  # noqa: ANN001
    """Character agent should prefer valid LLM output."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    payload = {
        "characters": [
            {
                "name": "Nasruddin",
                "role": "main",
                "description": "Wise advisor known for unconventional but insightful guidance to his neighbors.",
                "visual_traits": ["turban", "calm eyes"],
                "speech_style": "wry",
            },
            {
                "name": "Neighbor",
                "role": "supporting",
                "description": "Frustrated local man struggling with an overcrowded home and family stress.",
                "visual_traits": ["disheveled clothes", "anxious posture"],
                "speech_style": "emotional",
            },
        ]
    }
    monkeypatch.setattr(
        CharacterAgent,
        "_get_openai_client",
        lambda self, api_key: _FakeClient(json.dumps(payload)),
    )

    profiles = CharacterAgent().run(_story("Nasruddin advises his neighbor."))

    assert [profile.name for profile in profiles] == ["Nasruddin", "Neighbor"]
    assert [profile.role for profile in profiles] == ["main", "supporting"]
    assert profiles[0].speech_style == "wry"
    assert len(profiles[0].description.split()) <= 20


def test_character_agent_includes_unnamed_from_llm(monkeypatch) -> None:  # noqa: ANN001
    """Character agent should keep unnamed placeholders from LLM payload."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    payload = {
        "characters": [
            {
                "name": "Unnamed Character 1",
                "role": "background",
                "description": "Minor passerby with minimal impact on the core storyline.",
                "visual_traits": ["hooded figure"],
                "speech_style": "quiet",
            },
            {
                "name": "Nasruddin",
                "role": "main",
                "description": "Calm and witty advisor who guides others through paradoxical lessons.",
                "visual_traits": ["turban"],
                "speech_style": "wry",
            },
        ]
    }
    monkeypatch.setattr(
        CharacterAgent,
        "_get_openai_client",
        lambda self, api_key: _FakeClient(json.dumps(payload)),
    )

    profiles = CharacterAgent().run(_story("Nasruddin speaks to someone unnamed."))

    assert len(profiles) == 2
    assert profiles[0].name == "Unnamed Character 1"
    assert profiles[1].name == "Nasruddin"
    assert all(profile.description for profile in profiles)


def test_character_agent_falls_back_when_llm_fails(monkeypatch) -> None:  # noqa: ANN001
    """Character agent should fallback to deterministic extraction on LLM failure."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def _raise_client(self, api_key: str):  # noqa: ANN001
        _ = api_key
        raise RuntimeError("API unavailable")

    monkeypatch.setattr(CharacterAgent, "_get_openai_client", _raise_client)

    profiles = CharacterAgent().run(_story("Nasruddin meets Omar. Nasruddin advises Omar."))

    assert len(profiles) >= 1
    assert profiles[0].name in {"Nasruddin", "Omar"}
    assert all(profile.description for profile in profiles)


def test_character_timeout_default_and_env_override(monkeypatch) -> None:  # noqa: ANN001
    """Character API timeout should support env override with sane default."""

    agent = CharacterAgent()

    monkeypatch.delenv("COMIC_AGENT_CHARACTER_TIMEOUT_SECONDS", raising=False)
    assert agent._character_timeout_seconds() == 60.0

    monkeypatch.setenv("COMIC_AGENT_CHARACTER_TIMEOUT_SECONDS", "90")
    assert agent._character_timeout_seconds() == 90.0


def test_character_timeout_invalid_env_falls_back(monkeypatch) -> None:  # noqa: ANN001
    """Invalid timeout env should fallback to default timeout value."""

    monkeypatch.setenv("COMIC_AGENT_CHARACTER_TIMEOUT_SECONDS", "invalid")
    assert CharacterAgent()._character_timeout_seconds() == 60.0
