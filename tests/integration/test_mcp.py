import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
import json

async def main():
    async with sse_client("http://localhost:8000/mcp/sse") as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            for t in tools.tools:
                if t.name == "dell_enclosure_management":
                    print(json.dumps(t.inputSchema, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
