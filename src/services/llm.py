import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
_client = genai.Client(api_key=os.getenv("LLM_API_KEY"))
MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")

def ask_llm(system: str, user: str) -> str:
    r = _client.models.generate_content(
        model=MODEL, contents=user,
        config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=800))
    return r.text
