"""The shared Claude call, driven through the real SDK with a mock transport."""

import argparse
import json

import anthropic
import httpx2
import pytest

from sre_ai_toolkit import common


def _args(**overrides):
    parser = argparse.ArgumentParser()
    common.add_common_args(parser)
    args = parser.parse_args([])
    for k, v in overrides.items():
        setattr(args, k, v)
    return args


def _client(reply: dict, seen: list):
    def handler(request):
        seen.append(request)
        return httpx2.Response(200, json=reply)

    return anthropic.Anthropic(
        api_key="test",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )


def _reply(text="ok", stop_reason="end_turn", model="claude-opus-5-5"):
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [
            {"type": "thinking", "thinking": "", "signature": "sig"},
            {"type": "text", "text": text},
        ],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 1000, "output_tokens": 200},
    }


def test_defaults_and_request_shape(capsys):
    seen = []
    out = common.ask(_args(), system="s", user="u", client=_client(_reply("brief"), seen))
    assert out == "brief"  # text block found even though a thinking block leads
    body = json.loads(seen[0].content)
    assert body["model"] == "claude-opus-5-5"
    assert body["output_config"] == {"effort": "medium"}
    assert body["fallbacks"] == "default"
    assert "temperature" not in body
    assert "[usage] claude-opus-5-5: 1,000 in, 200 out · est. $" in capsys.readouterr().err


def test_json_schema_is_sent_as_structured_output():
    seen = []
    schema = {"type": "object", "properties": {}, "additionalProperties": False}
    common.ask(
        _args(), system="s", user="u", json_schema=schema, client=_client(_reply("{}"), seen)
    )
    assert json.loads(seen[0].content)["output_config"]["format"]["schema"] == schema


def test_dry_run_makes_no_call(capsys):
    assert common.ask(_args(dry_run=True), system="s", user="u", client=None) == ""
    assert json.loads(capsys.readouterr().out)["messages"][0]["content"] == "u"


def test_refusal_and_truncation_raise():
    with pytest.raises(common.ToolkitError, match="declined"):
        common.ask(_args(), system="s", user="u", client=_client(_reply("", "refusal"), []))
    with pytest.raises(common.ToolkitError, match="max-tokens"):
        common.ask(_args(), system="s", user="u", client=_client(_reply("x", "max_tokens"), []))


def test_no_fallback_param_for_models_without_it():
    seen = []
    common.ask(
        _args(model="claude-haiku-5-5"),
        system="s",
        user="u",
        client=_client(_reply(model="claude-haiku-5-5"), seen),
    )
    assert "fallbacks" not in json.loads(seen[0].content)


def test_cost_estimate_uses_cheaper_cache_reads_on_5_5():
    usage = type(
        "U", (), {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 1_000_000}
    )()
    assert common.estimate_usd("claude-sonnet-5-5", usage) == pytest.approx(0.10)
