import uuid


def sid():
    return "s-" + uuid.uuid4().hex[:8]


def chat(client, session, msg, headers=None, **extra):
    return client.post("/chat", json={"session_id": session, "message": msg, **extra},
                       headers=headers or {})


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "keys_configured": 2, "cache_enabled": True}


def test_live_then_cache_across_sessions(client):
    msg = "unique question " + uuid.uuid4().hex
    a = chat(client, sid(), msg).json()
    b = chat(client, sid(), msg).json()
    assert a["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert a["metadata"]["key_id"] == "key_1"
    assert b["metadata"]["resolution_source"] == "LLM_CACHE"
    assert b["metadata"]["key_id"] is None and b["metadata"]["fallback_attempts"] == 0
    assert a["reply"] == b["reply"]
    assert a["metadata"]["input_tokens"] == b["metadata"]["input_tokens"]


def test_different_message_not_cached(client):
    s = sid()
    assert chat(client, s, "hello " + uuid.uuid4().hex).json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert chat(client, s, "other " + uuid.uuid4().hex).json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"


def test_multi_turn_history_and_isolation(client, fake):
    s1, s2 = sid(), sid()
    chat(client, s1, "my name is Ada " + s1)
    chat(client, s1, "what is my name? " + s1)
    last_call = fake.calls[-1][1]
    assert [m["role"] for m in last_call] == ["system", "user", "assistant", "user"]
    h = client.get(f"/sessions/{s1}/messages").json()
    assert [m["role"] for m in h["messages"]] == ["user", "assistant", "user", "assistant"]
    assert "metadata" in h["messages"][1] and "metadata" not in h["messages"][0]
    chat(client, s2, "fresh " + s2)
    assert len(client.get(f"/sessions/{s2}/messages").json()["messages"]) == 2


def test_system_prompt_override(client, fake):
    chat(client, sid(), "hi " + uuid.uuid4().hex, system_prompt="Talk like a pirate")
    assert fake.calls[-1][1][0] == {"role": "system", "content": "Talk like a pirate"}


def test_simulated_failover(client):
    r = chat(client, sid(), "f1 " + uuid.uuid4().hex, {"X-Simulate-Failure": "key_1=429"})
    m = r.json()["metadata"]
    assert r.status_code == 200 and m["key_id"] == "key_2" and m["fallback_attempts"] == 1
    r = chat(client, sid(), "f2 " + uuid.uuid4().hex, {"X-Simulate-Failure": "key_1=500"})
    assert r.json()["metadata"]["key_id"] == "key_2"


def test_all_keys_fail_503_not_stored(client):
    s = sid()
    r = chat(client, s, "x", {"X-Simulate-Failure": "*=429"})
    assert r.status_code == 503 and r.json() == {"detail": "all providers unavailable"}
    assert client.get(f"/sessions/{s}/messages").status_code == 404


def test_real_provider_failure_falls_over(client, fake):
    fake.fail_keys.add("fake-a")
    r = chat(client, sid(), "real fail " + uuid.uuid4().hex)
    assert r.json()["metadata"]["key_id"] == "key_2"
    fake.fail_keys.add("fake-b")
    assert chat(client, sid(), "again " + uuid.uuid4().hex).status_code == 503


def test_validation(client):
    s = sid()
    assert client.post("/chat", json={"session_id": s, "message": "   "}).status_code == 422
    assert client.post("/chat", json={"session_id": s}).status_code == 422
    assert client.post("/chat", json={"message": "hi"}).status_code == 422
    assert client.post("/chat", json={"session_id": s, "message": "a" * 4001}).status_code == 422
    assert client.post("/chat", content="{bad", headers={"content-type": "application/json"}).status_code == 422
    assert client.get(f"/sessions/{s}/messages").status_code == 404


def test_unknown_session_404(client):
    r = client.get("/sessions/nope-" + sid() + "/messages")
    assert r.status_code == 404 and r.json() == {"detail": "session not found"}
