"""
Dell MCP — Ingestion & Clustering Runner CLI
============================================

Orchestrates Phase 1 OpenAPI specs parsing (stripping noise) and Phase 2 graph
construction and Leiden clustering, populating the SQLite governance database.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.ai_clustering.graph_clustering import run_pipeline
from src.core.database import init_db_sync, set_pipeline_status
from src.parser.openapi_parser import OpenAPIParser
from src.parser.graphql_parser import GraphQLParser
from src.parser.grpc_parser import gRPCParser
from src.parser.asyncapi_parser import AsyncAPIParser
from src.core.models import ContractA
from src.ai_clustering.explain import set_explain_mode, is_explain_mode, explain_print

logger = logging.getLogger(__name__)


def main() -> int:
    """Run the ingestion and clustering pipeline on the provided OpenAPI specification."""
    parser = argparse.ArgumentParser(
        description="Ingest and cluster OpenAPI endpoints."
    )
    parser.add_argument(
        "--specs",
        type=Path,
        nargs="+",
        default=[Path("tests/fixtures/mini_openapi.yaml")],
        help="Path(s) to the specification files or directories.",
    )
    parser.add_argument(
        "--explain-pipeline",
        action="store_true",
        help="Enable live pipeline explain mode to stream detailed stages to the terminal.",
    )
    parser.add_argument(
        "--show-all-endpoints",
        action="store_true",
        help="Print every endpoint discovered in explain mode.",
    )
    args = parser.parse_args()
    
    set_explain_mode(args.explain_pipeline)

    # Set up logging format
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    import time
    start_time = time.time()

    logger.info("Initializing SQLite database...")
    init_db_sync()

    spec_paths: list[Path] = args.specs
    # Expand directories
    expanded_paths = []
    for path in spec_paths:
        if path.is_dir():
            expanded_paths.extend([p for p in path.iterdir() if p.is_file()])
        elif path.exists():
            expanded_paths.append(path)

    if not expanded_paths:
        root_spec = Path("openapi.json")
        if root_spec.exists():
            expanded_paths = [root_spec]
        else:
            logger.error(f"No spec files found in the provided paths.")
            return 1

    try:
        set_pipeline_status("ingestionStatus", "running")
        all_endpoints = []
        spec_titles = []
        
        total_paths = 0
        total_ops = 0

        for path in expanded_paths:
            logger.info(f"Ingesting spec from: {path}")
            
            ext = path.suffix.lower()
            if ext in [".graphql", ".gql"]:
                parser_obj = GraphQLParser(path)
            elif ext == ".proto":
                parser_obj = gRPCParser(path)
            elif ext in [".yaml", ".yml", ".json"]:
                # Basic heuristic: could be OpenAPI or AsyncAPI
                # For now assume OpenAPI, AsyncAPI typically has "asyncapi" inside
                # But to meet requirements, let's look at content
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        head = f.read(500).lower()
                    if "asyncapi" in head:
                        parser_obj = AsyncAPIParser(path)
                    else:
                        parser_obj = OpenAPIParser(path)
                except:
                    parser_obj = OpenAPIParser(path)
            else:
                logger.warning(f"Unsupported file extension {ext} for {path}. Skipping.")
                continue

            contract_a = parser_obj.parse_and_flatten()
            all_endpoints.extend(contract_a.endpoints)
            spec_titles.append(contract_a.spec_title)
            
            # Simple approximation for stats since only OpenAPI accurately tracks raw paths
            total_paths += len(contract_a.endpoints)
            total_ops += len(contract_a.endpoints)

        # Merge all endpoints into a single unified ContractA pool
        merged_contract_a = ContractA(
            spec_title=" | ".join(spec_titles),
            spec_version="1.0.0",
            openapi_version="N/A",
            source_file="Multi-API",
            total_endpoints=len(all_endpoints),
            endpoints=all_endpoints
        )
        
        # ISSUE #1 - OPENAPI FILE STATS
        if is_explain_mode():
            total_endpoints = len(merged_contract_a.endpoints)
            
            content = (
                f"Paths Found: {total_paths}\n"
                f"Operations Found: {total_ops}\n"
                f"Endpoints Extracted: {total_endpoints}\n\n"
                f"FIRST 10 ENDPOINTS:\n"
            )
            for ep in merged_contract_a.endpoints[:10]:
                content += f"{ep.method} {ep.url}\n"
                
            content += "\nLAST 10 ENDPOINTS:\n"
            for ep in merged_contract_a.endpoints[-10:]:
                content += f"{ep.method} {ep.url}\n"
                
            explain_print("STAGE 1A — MULTI-API FILE STATS", content)
        else:
            pass # merged_contract_a already populated
        
        # STAGE 1: ENDPOINT EXTRACTION (ISSUE #2)
        if is_explain_mode() and args.show_all_endpoints:
            for i, ep in enumerate(merged_contract_a.endpoints, 1):
                req_params = "\n".join(p.name for p in ep.required_params) if ep.required_params else "None"
                tags_str = ", ".join(ep.tags) if ep.tags else "None"
                content = (
                    f"operation_id:\n{ep.operation_id}\n\n"
                    f"method:\n{ep.method}\n\n"
                    f"path:\n{ep.url}\n\n"
                    f"tags:\n{tags_str}\n\n"
                    f"summary:\n{ep.summary or ''}\n\n"
                    f"required_params:\n{req_params}"
                )
                explain_print(f"ENDPOINT #{i}", content)

        set_pipeline_status("ingestionStatus", "complete")

        set_pipeline_status("graphStatus", "running")
        set_pipeline_status("clusteringStatus", "running")
        logger.info("Building relationship graph and clustering endpoints...")
        
        # Run pipeline and pass total paths for stats
        stats = run_pipeline(merged_contract_a)
        if stats:
            stats["total_paths"] = total_paths if is_explain_mode() else len(merged_contract_a.endpoints) # approximation if not explain mode
            
        set_pipeline_status("graphStatus", "complete")
        set_pipeline_status("clusteringStatus", "complete")

        # Set default MCP server status
        set_pipeline_status("mcpRuntimeStatus", "complete")

        # FINAL PIPELINE REPORT (ISSUE #9)
        if is_explain_mode() and stats:
            duration = time.time() - start_time
            content = (
                f"OpenAPI Paths:\n{stats.get('total_paths', 0)}\n\n"
                f"Endpoints:\n{len(merged_contract_a.endpoints)}\n\n"
                f"Embeddings:\n{stats.get('embeddings_generated', 0)}\n\n"
                f"Graph Nodes:\n{stats.get('graph_nodes', 0)}\n\n"
                f"Graph Edges:\n{stats.get('graph_edges', 0)}\n\n"
                f"Communities:\n{stats.get('communities', 0)}\n\n"
                f"Workflows Generated:\n{stats.get('workflow_names', 0)}\n\n"
                f"LLM Success:\n{stats.get('llm_labels', 0)}\n\n"
                f"LLM Fallback:\n{stats.get('llm_fallbacks', 0)}\n\n"
                f"Saved:\n{stats.get('workflows_saved', 0)}\n\n"
                f"Duration:\n{duration:.1f} seconds\n"
            )
            explain_print("PIPELINE REPORT", content)

        logger.info("Ingestion and Graph-Clustering completed successfully.")
        return 0
    except Exception as err:
        logger.error(f"Pipeline failed: {err}")
        set_pipeline_status("ingestionStatus", "error")
        set_pipeline_status("graphStatus", "error")
        set_pipeline_status("clusteringStatus", "error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
