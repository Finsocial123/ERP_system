from dotenv import load_dotenv

load_dotenv()

import os
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)
