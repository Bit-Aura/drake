"""Provider-agnostic LLM service for structured workflow discovery responses."""

from __future__ import annotations

import logging
import os
from typing import Any

import instructor
from openai import OpenAI
from pydantic import BaseModel


class WorkflowValidationError(Exception):
    pass


class Settings:
    LLM_MODEL = os.environ.get("LLM_MODEL", "qwen2.5-coder:14b")
    LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "120.0"))
    LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "ollama")


settings = Settings()


class LLMServiceError(RuntimeError):
    """Raised when LLM communication fails."""


class WorkflowItem(BaseModel):
    display_name: str
    generated_description: str


class WorkflowMapping(BaseModel):
    workflows: list[WorkflowItem]


class LLMService:
    """Purpose: Communicate with LLM providers (OpenAI, LiteLLM, Ollama).

    Responsibilities:
        Send prompts, handle timeouts, and retrieve structured JSON.
    Inputs:
        Workflow discovery prompt strings.
    Outputs:
        Raw JSON objects that can validate as WorkflowMapping.
    """

    def __init__(
        self,
        model: str = settings.LLM_MODEL,
        timeout: float = settings.LLM_TIMEOUT,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize a provider-agnostic LLM client."""
        self._model = model
        self._timeout = timeout
        self._logger = logger or logging.getLogger(__name__)

        raw_client = OpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.OPENAI_API_KEY,
            timeout=timeout,
        )
        self._client = instructor.from_openai(raw_client, mode=instructor.Mode.JSON)

    def generate_workflow_mapping(self, prompt: str) -> dict[str, Any]:
        """Request structured JSON from the LLM."""
        self._logger.info(f"Sending clustering request to LLM ({self._model})...")
        
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                response_model=WorkflowMapping,
                max_retries=2,
            )
        except Exception as exc:
            raise LLMServiceError(f"LLM request failed: {exc}") from exc

        from drake.ai_clustering.explain import is_explain_mode, explain_print
        if is_explain_mode():
            explain_print("RAW LLM RESPONSE", response.model_dump_json(indent=2))

        return response.model_dump()

    def generate_text(self, prompt: str) -> str:
        """Request raw text from the LLM for chunking summaries."""
        self._logger.info(f"Sending text request to LLM ({self._model})...")
        
        try:
            # Bypass instructor parsing by not passing response_model
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise LLMServiceError(f"LLM text request failed: {exc}") from exc
