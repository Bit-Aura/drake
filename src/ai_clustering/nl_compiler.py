import os
import logging
import instructor
from openai import AsyncOpenAI
from src.core.models import WorkflowMapping

logger = logging.getLogger("dell_mcp_nl_compiler")

async def compile_nl_to_workflow(prompt: str) -> WorkflowMapping:  # noqa: E302
    """
    Ingest a natural language prompt and use the local LLM engine via the instructor
    library to ensure a structured, strongly-typed WorkflowMapping JSON output.
    """
    api_key = os.getenv("OPENAI_API_KEY", "mock_key_for_local")
    base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    model_name = os.getenv("LLM_MODEL", "llama3")

    try:
        client = instructor.from_openai(AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=30.0))  # noqa: E501

        workflow_mapping = await client.chat.completions.create(
            model=model_name,
            response_model=WorkflowMapping,
            messages=[
                {
                    "role": "system",
                    "content": "You are a senior enterprise software architect. Convert the user's intent into a structured deterministic sequence of API calls."  # noqa: E501
                },
                {"role": "user", "content": prompt},
            ],
            max_retries=3
        )
        return workflow_mapping
    except Exception as e:
        logger.error(f"Failed to compile NL prompt to workflow: {e}")
        raise ValueError(f"NL Compiler Error: {e}")
