import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.tools.web_search import web_search

async def execute_tool(tool_name: str, tool_args: dict, db: AsyncSession) -> str:
    """
    Execute a tool call from the LLM and return result as string
    """

    if tool_name == "web_search":
        query = tool_args.get("query")
        print(f"QUERY: ", {query})
        if not query:
            return json.dumps({"error": "No query provided"})
        try:
            result = await web_search(query=query)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e), "query": query})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})

