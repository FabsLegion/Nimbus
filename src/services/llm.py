"""LLM gateway: provider chain with failover. Same ask_llm(system, user) signature, so nothing else changes.
Configure in .env, e.g.
  LLM_PROVIDERS=gemini,groq
  GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
  GEMINI_KEYS=key1,key2        GEMINI_MODEL=gemini-2.5-flash
  GROQ_BASE_URL=https://api.groq.com/openai/v1   GROQ_KEYS=...   GROQ_MODEL=openai/gpt-oss-120b
Check model names in each provider's console; they change."""
import os, time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
_cool = {}   # (provider, key) -> time until which it is skipped after a failure
LOG = []     # recent calls: provider, seconds, ok

def _chain():
    for p in os.getenv("LLM_PROVIDERS", "gemini").split(","):
        P = p.strip().upper()
        for key in os.getenv(f"{P}_KEYS", "").split(","):
            if key.strip():
                yield p.strip(), P, key.strip()

def ask_llm(system: str, user: str, max_tokens: int = 800) -> str:
    last = None
    for p, P, key in _chain():
        if _cool.get((p, key), 0) > time.time():
            continue
        t = time.time()
        try:
            r = OpenAI(base_url=os.getenv(f"{P}_BASE_URL"), api_key=key, timeout=20).chat.completions.create(
                model=os.getenv(f"{P}_MODEL"), max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
            LOG.append({"provider": p, "sec": round(time.time() - t, 2), "ok": True})
            return r.choices[0].message.content
        except Exception as e:                    # 429, 5xx, bad key, model removed: try the next one
            _cool[(p, key)] = time.time() + 60
            LOG.append({"provider": p, "sec": round(time.time() - t, 2), "ok": False})
            last = e
    raise RuntimeError(f"all providers failed: {last}")
