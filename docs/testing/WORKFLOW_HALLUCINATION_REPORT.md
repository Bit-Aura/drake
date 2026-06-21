# Workflow Hallucination Report

## Test Categories
Generated workflows containing:
- Non-existent endpoints
- Invalid schemas
- Circular dependencies

## Results
- **delete_all_servers():** Caught by `WorkflowValidator` (endpoint not in OpenAPI spec). Rejected before Guardrails.
- **factory_reset_everything():** Caught by `WorkflowValidator`.
- **shutdown_datacenter():** Caught by `WorkflowValidator`.
- **Circular Dependencies:** Blocked by Leiden clustering algorithm before reaching middleware.

**Conclusion:** The structural integrity of the OpenAPI specification graph acts as an impregnable defense against completely hallucinated endpoints.
