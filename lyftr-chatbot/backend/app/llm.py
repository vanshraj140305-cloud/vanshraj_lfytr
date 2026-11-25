"""LiteLLM gateway: key-pool failover + built-in response cache."""
import logging
import time
from typing import Optional

import litellm

from . import config

log = logging.getLogger("llm")
litellm.drop_params = True
litellm.suppress_debug_info = True


class AllProvidersUnavailable(Exception):
    pass


def setup_cache() -> None:
    """Enable LiteLLM's built-in cache. Key = model + messages (+ fixed params)."""
    if config.cache_type() == "disk":
        litellm.cache = litellm.Cache(type="disk", disk_cache_dir=config.cache_dir())
    else:
        litellm.cache = litellm.Cache(type="local")


def cache_enabled() -> bool:
    return litellm.cache is not None


def parse_simulation(header: Optional[str]) -> dict[str, int]:
    """'key_1=429,key_2=500' or '*=429' -> {'key_1': 429, ...}. Bad pairs are ignored."""
    sim: dict[str, int] = {}
    if not header:
        return sim
    for pair in header.split(","):
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        k, v = k.strip(), v.strip()
        if v in {"429", "500", "502", "503"} and k:
            sim[k] = int(v)
    return sim


async def generate(messages: list[dict], simulation: dict[str, int]) -> dict:
    """Try each key in order. Returns reply + provider info, or raises AllProvidersUnavailable."""
    model = config.model()
    failed = 0
    # A simulated request must exercise the live provider path, so skip the cache for it.
    use_cache = not simulation

    for idx, key in enumerate(config.api_keys(), start=1):
        key_id = f"key_{idx}"
        status = simulation.get(key_id, simulation.get("*"))
        if status is not None:
            log.warning("simulated %s for %s", status, key_id)
            failed += 1
            continue
        try:
            resp = await litellm.acompletion(
                model=model,
                messages=messages,
                api_key=key,
                caching=use_cache,
                num_retries=0,
                timeout=30,
                max_tokens=config.max_output_tokens(),
            )
            text = (resp.choices[0].message.content or "").strip()
            if not text:
                raise ValueError("empty completion")
        except Exception as exc:  # 429, quota, 5xx, timeouts, auth -> next key
            log.warning("%s failed (%s): %s", key_id, type(exc).__name__, str(exc)[:200])
            failed += 1
            continue

        hit = bool((getattr(resp, "_hidden_params", None) or {}).get("cache_hit"))
        usage = getattr(resp, "usage", None)
        return {
            "reply": text,
            "cache_hit": hit,
            "model": model,
            "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "key_id": None if hit else key_id,
            "fallback_attempts": 0 if hit else failed,
        }
    raise AllProvidersUnavailable()
