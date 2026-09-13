import os
import re
import logging
from google import genai
from google.genai import types
from app.agent.tools import ALL_TOOLS
from app.agent.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_api_keys: list[str] = []
_current_key_idx: int = 0
_client = None

def _load_keys() -> list[str]:
    raw = os.environ.get("GEMINI_API_KEY", "")
    keys = [k.strip() for k in re.split(r"[,;\n]", raw) if k.strip()]
    return keys

def _get_http_options() -> types.HttpOptions:
    return types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1))

def get_current_client() -> genai.Client:
    global _client, _api_keys, _current_key_idx
    if not _api_keys:
        _api_keys = _load_keys()
        if not _api_keys:
            raise ValueError("GEMINI_API_KEY is missing in environment.")
        _current_key_idx = 0
        _client = genai.Client(api_key=_api_keys[_current_key_idx], http_options=_get_http_options())
    elif _client is None:
        _client = genai.Client(api_key=_api_keys[_current_key_idx], http_options=_get_http_options())
    return _client

def rotate_api_key() -> bool:
    """Rotates to the next available API key if multiple keys are configured.
    Returns True if rotated to a new key, False if only 1 key is available.
    """
    global _client, _api_keys, _current_key_idx
    if not _api_keys:
        _api_keys = _load_keys()

    if len(_api_keys) <= 1:
        logger.warning("Only 1 GEMINI_API_KEY configured; cannot rotate.")
        return False

    _current_key_idx = (_current_key_idx + 1) % len(_api_keys)
    masked_key = _api_keys[_current_key_idx][:6] + "..." + _api_keys[_current_key_idx][-4:]
    logger.info(f"Rotated to Gemini API key index {_current_key_idx + 1}/{len(_api_keys)} ({masked_key})")
    _client = genai.Client(api_key=_api_keys[_current_key_idx], http_options=_get_http_options())
    return True

def get_chat_session(history=None):
    """Initializes and returns a Google GenAI Chat Session configured with our tools and system prompt."""
    client = get_current_client()
    config = types.GenerateContentConfig(
        tools=ALL_TOOLS,
        system_instruction=SYSTEM_PROMPT,
        temperature=0.0,
    )
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
    chat = client.chats.create(
        model=model_name,
        config=config,
        history=history,
    )
    return chat

