from types import SimpleNamespace
from unittest.mock import Mock

import litellm
import pytest

from seoci.config import settings
from seoci.providers.llm import Intent, LiteLLMClient


@pytest.mark.parametrize("api_base", ["", "http://localhost:8080/v1"])
@pytest.mark.parametrize("repair", [False, True])
def test_completion_optional_api_base(monkeypatch, api_base, repair):
    monkeypatch.setattr(settings, "llm_model", "openai/custom-model")
    monkeypatch.setattr(settings, "llm_api_base", api_base)
    content = '{"label":"informational","reason":"Guide","confidence":0.8}'
    contents = ['{"label":"invalid"}', content] if repair else [content]
    completion = Mock(side_effect=[
        SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            choices=[SimpleNamespace(message=SimpleNamespace(content=value))],
        )
        for value in contents
    ])
    monkeypatch.setattr(litellm, "completion", completion)
    monkeypatch.setattr(litellm, "completion_cost", lambda **kwargs: 0)

    assert LiteLLMClient().complete_json("intent", "test", Intent).label == "informational"
    assert completion.call_count == len(contents)
    for call in completion.call_args_list:
        assert call.kwargs["model"] == "openai/custom-model"
        if api_base:
            assert call.kwargs["api_base"] == api_base
        else:
            assert "api_base" not in call.kwargs


def test_completion_preserves_response_when_pricing_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "llm_model", "openai/custom-model")
    monkeypatch.setattr(settings, "llm_api_base", "http://localhost:8080/v1")
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        choices=[SimpleNamespace(message=SimpleNamespace(
            content='{"label":"informational","reason":"Guide","confidence":0.8}',
        ))],
    )
    completion = Mock(return_value=response)
    cost = Mock(side_effect=Exception("Model not found in cost map"))
    monkeypatch.setattr(litellm, "completion", completion)
    monkeypatch.setattr(litellm, "completion_cost", cost)

    llm = LiteLLMClient()
    assert llm.complete_json("intent", "test", Intent).label == "informational"
    completion.assert_called_once()
    cost.assert_called_once_with(completion_response=response)
    assert llm.usage == [{
        "task": "intent", "model": "openai/custom-model",
        "prompt_tokens": 10, "completion_tokens": 5, "cost_usd": 0,
    }]
