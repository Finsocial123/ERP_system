import os
from tavily import AsyncTavilyClient
from app.core.config import settings
import asyncio

tavily = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)

async def web_search(query: str) -> dict:
    try:
        response = await asyncio.wait_for(
            tavily.search(query, max_result=3),
            timeout=5.0,
        )
        # response = await tavily.search(query, max_results=3)
        print(f"TAVILY RESPONSE: {response}")
        results = [
            {
                "title": res["title"],
                "url": res["url"],
                "content": res["content"][:500],
            }
            for res in response["results"]
        ]
    except asyncio.TimeoutError:
        return {"query": query, "results": []}
    except Exception as e:
        print(f"TAVILY RESPONSE: {str(e)}")
        return {"query": query, "results": []}
    return {"query": query, "results": results}