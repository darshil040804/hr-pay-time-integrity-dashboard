"""Offline tests for ai/client.py helpers. No API calls are made."""

import pytest

from ai.client import AIConfigError, load_config, parse_json, strip_code_fences


@pytest.mark.parametrize("reply", [
    '{"ok": true}',
    '```json\n{"ok": true}\n```',
    '```\n{"ok": true}\n```',
    'Here you go:\n```json\n{"ok": true}\n```\nLet me know if you need more.',
    '  ```JSON {"ok": true} ```  ',
])
def test_parse_json_strips_code_fences(reply):
    assert parse_json(reply) == {"ok": True}


def test_strip_code_fences_leaves_plain_text_alone():
    assert strip_code_fences('  [1, 2]  ') == "[1, 2]"


def _set_env(monkeypatch, **values):
    for name in ["AI_BASE_URL", "AI_API_KEY", "AI_MODEL", "AI_REQUEST_DELAY_SECONDS"]:
        monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_request_delay_defaults_to_3_seconds(monkeypatch):
    _set_env(monkeypatch, AI_BASE_URL="http://example.test", AI_API_KEY="k", AI_MODEL="m")
    assert load_config()["request_delay"] == 3.0


def test_request_delay_reads_env(monkeypatch):
    _set_env(monkeypatch, AI_BASE_URL="http://example.test", AI_API_KEY="k", AI_MODEL="m",
             AI_REQUEST_DELAY_SECONDS="7.5")
    assert load_config()["request_delay"] == 7.5


def test_placeholder_key_is_rejected_without_echoing_it(monkeypatch):
    _set_env(monkeypatch, AI_BASE_URL="http://example.test", AI_API_KEY="your-key-here", AI_MODEL="m")
    with pytest.raises(AIConfigError, match="AI_API_KEY") as error:
        load_config()
    assert "your-key-here" not in str(error.value)
