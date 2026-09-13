import os
from google import genai
from google.genai import types
from app.agent.tools import ALL_TOOLS
from app.agent.prompts import SYSTEM_PROMPT

_client = None

def get_chat_session():
    """Initializes and returns a Google GenAI Chat Session configured with our tools and system prompt."""
    global _client
    
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing in environment.")
        _client = genai.Client(api_key=api_key)
    
    config = types.GenerateContentConfig(
        tools=ALL_TOOLS,
        system_instruction=SYSTEM_PROMPT,
        temperature=0.0,
    )
    
    chat = _client.chats.create(
        model="gemini-2.5-flash",
        config=config
    )
    
    return chat
