import asyncio
import sys
import os
import logging

# Ensure project root is in the python path for execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from drake.proxy.server import mcp, load_approved_tools_from_db
from drake.core.database import get_db, WorkflowLog, init_db, PendingWorkflow, init_db_sync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dell_mcp_stdio")

async def setup():  # noqa: E302
    logger.info("Initializing stdio server database and loading approved tools...")
    init_db_sync()
    await init_db()

    try:
        from drake.core.database import sync_governance_to_mcp_proxy
        await sync_governance_to_mcp_proxy()
    except Exception as e:
        logger.warning(f"Failed to sync governance db: {e}")

    await load_approved_tools_from_db()

def main():  # noqa: E302
    # Run setup in an isolated event loop to prepare DB and register tools
    asyncio.run(setup())

    # Run the FastMCP server over stdio
    logger.info("Starting FastMCP server over stdio transport...")
    mcp.run(transport="stdio")

if __name__ == "__main__":  # noqa: E305
    main()
