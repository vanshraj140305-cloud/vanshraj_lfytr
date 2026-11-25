# LLM Chatbot with Key Failover and Response Caching

React + FastAPI + SQLite, with LiteLLM for caching and a multi-key failover pool.

## 1. Live URLs
- Frontend: _add URL_
- Backend: _add URL_ (`/health`)
- Demo video: _add URL_

## 2. Run locally

**With Docker**
```bash
cp .env.example .env     # put at least 2 real keys in LLM_API_KEYS
make up                  # frontend :3000, backend :8000
make down
```

**Without Docker**
```bash
# backend
cd backend && pip install -r requirements.txt
export LLM_API_KEYS=key1,key2 DATABASE_URL=sqlite:///./app.db ENABLE_FAILURE_SIMULATION=true
uvicorn app.main:app --port 8000
# tests (no real keys needed, LiteLLM is stubbed)
python -m pytest
# frontend
cd frontend && npm install && VITE_API_URL=http://localhost:8000 npm run dev
```

**Deploying:** backend on Render/Railway/Fly with a persistent disk mounted at `/data`; set `LLM_API_KEYS`, `DATABASE_URL=sqlite:////data/app.db`, `ALLOWED_ORIGINS=<frontend URL>`, `ENABLE_FAILURE_SIMULATION=true`. Frontend on Vercel/Netlify with build env `VITE_API_URL=<backend URL>`.

## 3. Design decisions
- **Key fallback:** `LLM_API_KEYS` is parsed into `key_1..key_n`. For each request, keys are tried in order through `litellm.acompletion(api_key=...)`. Any exception (429, quota, 5xx, timeout, empty reply) moves on to the next key; `fallback_attempts` counts failures. If every key fails the API returns `503 {"detail":"all providers unavailable"}` and nothing is written to history. Keys are never returned, only ids.
- **Caching:** LiteLLM's built-in cache (`litellm.Cache`, in-memory by default, `CACHE_TYPE=disk` for disk). The key is model + full message list (system + history + new message), so the same first message in a new session hits, and any different message misses. Hits report `LLM_CACHE`, `key_id: null`, `fallback_attempts: 0`, and the token usage stored with the cached response.
- **Simulation hook:** `X-Simulate-Failure` is parsed only if `ENABLE_FAILURE_SIMULATION=true`. Listed keys are skipped as failed for that request only. Simulated requests bypass the cache so failover is always demonstrable, and the answer is still a real LLM call.
- **SQLite:** `messages` table as specified, plus a `sessions` table holding the per-session system prompt. Schema is created at startup; file lives at `DATABASE_URL` on a Docker volume. A user/assistant pair is written only after a successful reply, so failed requests leave no trace. The system prompt is never returned by the history endpoint.
- **Tokens/latency:** taken from the single response's `usage` (per request, never cumulative); latency is measured server-side with `perf_counter`.

## 4. Verification
```bash
B=http://localhost:8000
curl $B/health
# live then cache (new session, same first message)
curl -s $B/chat -H 'content-type: application/json' -d '{"session_id":"a1","message":"Capital of France?"}'
curl -s $B/chat -H 'content-type: application/json' -d '{"session_id":"a2","message":"Capital of France?"}'   # LLM_CACHE
# failover
curl -s $B/chat -H 'content-type: application/json' -H 'X-Simulate-Failure: key_1=429' -d '{"session_id":"a3","message":"hello"}'   # key_2
curl -s -i $B/chat -H 'content-type: application/json' -H 'X-Simulate-Failure: *=429' -d '{"session_id":"a3","message":"hello"}'     # 503
curl $B/sessions/a1/messages
```
In the UI, expand **Session settings** and type `key_1=429` into "Simulate failure" to demo failover. Each reply shows source, model, latency and per-request tokens.

## 5. Setup Used
Editor: _add_. AI tools: Claude (scaffolding and review).

## 6. Bonus features
- Per-session system prompt field in the UI.
- Failure-simulation field in the UI for demos.
- Optional disk cache (`CACHE_TYPE=disk`).
