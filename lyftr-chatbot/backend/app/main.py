import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config, db, llm
from .schemas import ChatRequest

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    llm.setup_cache()
    yield


app = FastAPI(title="LLM Chatbot", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.allowed_origins(),
    allow_methods=["*"],
    allow_headers=["*"],  # includes X-Simulate-Failure
)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    logging.exception("unhandled error")
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


@app.get("/health")
def health():
    keys = len(config.api_keys())
    ok = db.ping() and keys > 0
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ok" if ok else "degraded", "keys_configured": keys,
                 "cache_enabled": llm.cache_enabled()},
    )


@app.post("/chat")
async def chat(req: ChatRequest,
               x_simulate_failure: Optional[str] = Header(default=None)):
    start = time.perf_counter()
    simulation = llm.parse_simulation(x_simulate_failure) if config.simulation_enabled() else {}

    system_prompt = (req.system_prompt or "").strip() or db.get_system_prompt(req.session_id) \
        or config.default_system_prompt()
    messages = [{"role": "system", "content": system_prompt}]
    messages += db.get_history(req.session_id)
    messages.append({"role": "user", "content": req.message})

    try:
        result = await llm.generate(messages, simulation)
    except llm.AllProvidersUnavailable:
        return JSONResponse(status_code=503, content={"detail": "all providers unavailable"})

    latency_ms = max(1, int((time.perf_counter() - start) * 1000))
    metadata = {
        "resolution_source": "LLM_CACHE" if result["cache_hit"] else "LIVE_INFERENCE",
        "model": result["model"],
        "latency_ms": latency_ms,
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "key_id": result["key_id"],
        "fallback_attempts": result["fallback_attempts"],
    }
    db.save_turn(req.session_id, req.message, result["reply"], metadata,
                 (req.system_prompt or "").strip() or None)
    return {"session_id": req.session_id, "reply": result["reply"], "metadata": metadata}


@app.get("/sessions/{session_id}/messages")
def session_messages(session_id: str):
    msgs = db.get_messages(session_id)
    if not msgs:
        return JSONResponse(status_code=404, content={"detail": "session not found"})
    return {"session_id": session_id, "messages": msgs}
