import os
from tavily import AsyncTavilyClient
from app.core.config import settings

tavily = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)

async def web_search(query: str) -> dict:
    try:
        response = await tavily.search(query, max_results=3)
        print(f"TAVILY RESPONSE: {response}")
        results = [
            {
                "title": res["title"],
                "url": res["url"],
                "content": res["content"],
            }
            for res in response["results"]
        ]
    except Exception as e:
        print(f"TAVILY RESPONSE: {str(e)}")
        raise
    return {"query": query, "results": results}