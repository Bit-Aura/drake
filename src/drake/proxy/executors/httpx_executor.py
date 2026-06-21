import logging
import re
import os
import hashlib
import time
import asyncio
from dataclasses import dataclass
from typing import Any, Dict
import json
import httpx
from urllib.parse import urljoin, quote
from tenacity import (
    AsyncRetrying,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
)
from drake.proxy.executors.base import BaseExecutor
from drake.core.exceptions import DellProxyExecutionError
from drake.core.compression import compress_redfish_response
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from drake.core.database import async_session, Workflow

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    response_dict: dict
    expires_at: float

_execution_cache: Dict[str, CacheEntry] = {}
_cache_lock = asyncio.Lock()
_pending_requests: Dict[str, asyncio.Event] = {}

def resolve_expressions(value: Any, context: dict) -> Any:
    """
    Recursively resolves {{step.key}} expressions in strings, dicts, or lists
    using the provided context dictionary.
    """
    if isinstance(value, str):
        def repl(match):
            path = match.group(1).split('.')
            cur = context
            for p in path:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    return match.group(0)
            return str(cur)
        return re.sub(r"\{\{([\w\.]+)\}\}", repl, value)
    elif isinstance(value, dict):
        return {k: resolve_expressions(v, context) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_expressions(i, context) for i in value]
    return value


class HTTPXExecutorBase(BaseExecutor):
    """
    Base HTTPX execution engine that implements true orchestration, variable passing,
    proper URL construction, and error handling.
    """
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session_headers: Dict[str, str] = {}
        
    async def authenticate(self) -> bool:
        """Base HTTPX Executor doesn't dictate auth. Subclasses should override."""
        return True
        
    async def healthcheck(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(self.base_url, timeout=5.0)
                return res.status_code < 500
        except Exception:
            return False

    async def execute_step(self, step: Any, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a single step. Outputs become variables for future steps.
        Proper URL encoding is used instead of basic string replacement.
        """
        # Resolve any context expressions in the parameters
        resolved_params = resolve_expressions(params, context)

        # Build path carefully with url encoding
        path = step.url
        path_matches = re.findall(r"\{([a-zA-Z0-9_]+)\}", path)
        for match in path_matches:
            if match in resolved_params:
                # Use proper url encoding and prevent path traversal
                encoded_val = quote(str(resolved_params[match]), safe="")
                path = re.sub(rf"\{{{match}\}}", encoded_val, path)
            elif f"workflow.input.{match}" in context.get("workflow", {}).get("input", {}):
                encoded_val = quote(str(context["workflow"]["input"][f"workflow.input.{match}"]), safe="")
                path = re.sub(rf"\{{{match}\}}", encoded_val, path)

        target_url = urljoin(self.base_url + "/", path.lstrip("/"))

        # Extract body parameters (anything not used in path)
        body_params = {k: v for k, v in resolved_params.items() if k not in path_matches}

        # Filter query/body params to only include parameters explicitly required/supported by this step
        if hasattr(step, "required_params") and step.required_params:
            try:
                supported_names = set()
                req_params_list = json.loads(step.required_params)
                for p in req_params_list:
                    if isinstance(p, dict) and "name" in p:
                        supported_names.add(p["name"])
                body_params = {k: v for k, v in body_params.items() if k in supported_names}
            except Exception as e:
                logger.exception(f"Failed to parse body: {e}")

        req_kwargs = {"timeout": 10.0, "headers": self.session_headers.copy()}
        if step.method.lower() in ["post", "put", "patch"]:
            req_kwargs["json"] = body_params
        elif step.method.lower() in ["get", "delete", "head"] and body_params:
            req_kwargs["params"] = body_params

        # Caching optimization
        is_get = step.method.lower() == "get"
        cache_key = None
        if is_get:
            # Build cache key
            key_content = f"{target_url}|{json.dumps(req_kwargs.get('params', {}), sort_keys=True)}|{json.dumps(req_kwargs.get('headers', {}), sort_keys=True)}"
            cache_key = hashlib.sha256(key_content.encode()).hexdigest()
            
            while True:
                async with _cache_lock:
                    if cache_key in _execution_cache:
                        entry = _execution_cache[cache_key]
                        if time.time() < entry.expires_at:
                            logger.info(f"Cache hit for GET {target_url}")
                            res = entry.response_dict.copy()
                            res["cached"] = True
                            return res
                        else:
                            del _execution_cache[cache_key]
                    
                    if cache_key in _pending_requests:
                        event = _pending_requests[cache_key]
                    else:
                        event = asyncio.Event()
                        _pending_requests[cache_key] = event
                        break
                await event.wait()

        def is_retryable_status_error(exc: BaseException) -> bool:
            if isinstance(exc, httpx.HTTPStatusError):
                return exc.response.status_code == 429 or exc.response.status_code >= 500
            return False

        retry_condition = retry_if_exception_type(httpx.TimeoutException) | retry_if_exception(is_retryable_status_error)

        async with httpx.AsyncClient() as client:
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=1, max=10),
                    retry=retry_condition,
                    reraise=True,
                ):
                    with attempt:
                        response = await client.request(step.method.upper(), target_url, **req_kwargs)
                        response.raise_for_status()

                        try:
                            data = response.json()
                            data = compress_redfish_response(data)
                        except ValueError:
                            data = {"raw": response.text}
                            
                        res_dict = {
                            "step_id": step.id,
                            "method": step.method.upper(),
                            "url": target_url,
                            "status_code": response.status_code,
                            "data": data,
                        }
                        
                        if is_get:
                            ttl = int(os.getenv("DELL_CACHE_TTL", "60"))
                            async with _cache_lock:
                                _execution_cache[cache_key] = CacheEntry(
                                    response_dict=res_dict,
                                    expires_at=time.time() + ttl
                                )
                                if cache_key in _pending_requests:
                                    _pending_requests[cache_key].set()
                                    del _pending_requests[cache_key]
                                
                        return res_dict
            except Exception as e:
                logger.exception(f"Error during step '{step.url}' execution: {e}")
                raise DellProxyExecutionError(
                    f"Workflow step execution failed for '{target_url}' after exhausting retries.",
                    original_exception=e,
                )
            finally:
                if is_get:
                    async with _cache_lock:
                        if cache_key in _pending_requests:
                            _pending_requests[cache_key].set()
                            del _pending_requests[cache_key]

    async def execute_workflow(self, workflow_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Executing workflow '{workflow_name}' via {self.__class__.__name__}")
        await self.authenticate()

        async with async_session() as session:
            result = await session.execute(
                select(Workflow).where(Workflow.system_name == workflow_name).options(selectinload(Workflow.steps)).limit(1)
            )
            wf = result.scalar_one_or_none()
            if not wf:
                raise DellProxyExecutionError(f"Workflow '{workflow_name}' not found.")
            steps = wf.steps

        # Initialize workflow context with input parameters
        context = {
            "workflow": {
                "input": params
            }
        }
        
        step_results = []
        for idx, step in enumerate(steps):
            step_name = step.operation_id
            
            # Variable Mapping Engine: Merge dynamically mapped inputs
            step_bindings = json.loads(step.variable_bindings) if step.variable_bindings else {}
            merged_params = params.copy()
            merged_params.update(step_bindings)

            try:
                res = await self.execute_step(step, merged_params, context)
                step_results.append(res)
                # Store output in context for future steps
                context[step_name] = res["data"]
            except Exception as e:
                error_msg = json.dumps({
                    "workflow_id": wf.id,
                    "status": "partial_failure",
                    "steps_executed": len(step_results),
                    "failed_step": step_name,
                    "error": str(e)
                })
                raise DellProxyExecutionError(f"Workflow failed at step {step_name}: {error_msg}")

        return {
            "workflow_id": wf.id,
            "status": "success",
            "steps_executed": len(step_results),
            "step_results": step_results,
            "context": context
        }


class PrismExecutor(HTTPXExecutorBase):
    """
    Execution engine for Hackathon environment targeting the Stoplight Prism mock server.
    """
    def __init__(self, base_url: str = "http://localhost:4010") -> None:
        super().__init__(base_url)

    async def authenticate(self) -> bool:
        # Inject dynamic auth token to satisfy Redfish security requirements
        token = os.getenv("MOCK_AUTH_TOKEN")
        if not token:
            if os.getenv("DELL_ENV", "development").lower() == "production":
                raise EnvironmentError("MOCK_AUTH_TOKEN is required in production environment.")
            token = "Basic YWRtaW46Y2Fsdmlu"
        self.session_headers["Authorization"] = token
        self.session_headers["X-Auth-Token"] = "prism-mock-token"
        return True


class MockExecutor(HTTPXExecutorBase):
    """
    Offline Mock Executor for fallback scenarios when Prism is not available.
    """
    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        super().__init__(base_url)

    async def authenticate(self) -> bool:
        token = os.getenv("MOCK_AUTH_TOKEN")
        if not token:
            if os.getenv("DELL_ENV", "development").lower() == "production":
                raise EnvironmentError("MOCK_AUTH_TOKEN is required in production environment.")
            token = "Basic mock-offline-token"
        self.session_headers["Authorization"] = token
        return True

# For backwards compatibility during transition
MockHTTPXExecutor = MockExecutor
