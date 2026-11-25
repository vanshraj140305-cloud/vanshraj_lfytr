import os
import tempfile
from types import SimpleNamespace

import pytest

os.environ["LLM_API_KEYS"] = "fake-a,fake-b"
os.environ["ENABLE_FAILURE_SIMULATION"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app import llm  # noqa: E402
from app.main import app  # noqa: E402


def make_response(text, pt, ct, hit):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=pt, completion_tokens=ct),
        _hidden_params={"cache_hit": hit},
    )


@pytest.fixture
def fake(monkeypatch):
    state = SimpleNamespace(cache={}, calls=[], fail_keys=set())

    async def fake_acompletion(model, messages, api_key, caching=True, **kw):
        ck = (model, repr(messages))
        if caching and ck in state.cache:
            text, pt, ct = state.cache[ck]
            return make_response(text, pt, ct, True)
        if api_key in state.fail_keys:
            raise RuntimeError("429 rate limited")
        state.calls.append((api_key, messages))
        last = messages[-1]["content"]
        words = sum(len(m["content"].split()) for m in messages)
        text = f"echo: {last}"
        if caching:
            state.cache[ck] = (text, words, 3)
        return make_response(text, words, 3, False)

    monkeypatch.setattr(llm.litellm, "acompletion", fake_acompletion)
    return state


@pytest.fixture
def client(fake):
    with TestClient(app) as c:
        yield c
