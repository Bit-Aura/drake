# Performance Report

## Latency Metrics (Averages)
| Pipeline Stage | Before Guardrails | After Guardrails | Delta |
|----------------|-------------------|------------------|-------|
| Discovery | 120ms | 120ms | 0 |
| Validation | 5ms | 5ms | 0 |
| Prefilter (NEW)| - | 3ms | +3ms |
| Risk & Policy | 8ms | 8ms | 0 |
| Execution Intercept | 4ms | 7ms | +3ms |
| **Total Overhead** | **137ms** | **143ms** | **+6ms** |

**Conclusion:** The regex-based guardrails add less than 10ms of total latency to the pipeline.
