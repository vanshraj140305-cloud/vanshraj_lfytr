"""All configuration comes from environment variables (read lazily so tests can override)."""
import os

DEFAULT_SYSTEM_PROMPT = "You are a helpful, concise assistant."


def api_keys() -> list[str]:
    return [k.strip() for k in os.getenv("LLM_API_KEYS", "").split(",") if k.strip()]


def model() -> str:
    return os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash")


def database_path() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:////data/app.db")
    # sqlite:////data/app.db -> /data/app.db ; sqlite:///app.db -> app.db
    return url.removeprefix("sqlite:///") if url.startswith("sqlite:///") else url


def allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]


def simulation_enabled() -> bool:
    return os.getenv("ENABLE_FAILURE_SIMULATION", "false").strip().lower() == "true"


def default_system_prompt() -> str:
    return os.getenv("DEFAULT_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)


def cache_type() -> str:
    return os.getenv("CACHE_TYPE", "local")  # "local" (in-memory) or "disk"


def cache_dir() -> str:
    return os.getenv("CACHE_DIR", "/data/llm_cache")


def max_output_tokens() -> int:
    return int(os.getenv("MAX_OUTPUT_TOKENS", "1024"))
