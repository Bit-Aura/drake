from pathlib import Path
from typing import Dict, Any

from src.cli.exceptions import DellCLIError
from src.core.database import get_db_connection, init_db_sync
from src.parser.openapi_parser import OpenAPIParser
from src.parser.graphql_parser import GraphQLParser
from src.parser.grpc_parser import gRPCParser
from src.parser.asyncapi_parser import AsyncAPIParser
from src.core.models import ContractA
from src.ai_clustering.graph_clustering import run_pipeline


class ClusterCLIService:
    """Adapter for spec ingestion and Leiden AI clustering services."""

    def run_clustering(self, spec_paths: list[Path], explain: bool) -> Dict[str, Any]:
        expanded_paths = []
        for path in spec_paths:
            if path.is_dir():
                expanded_paths.extend([p for p in path.iterdir() if p.is_file()])
            elif path.exists():
                expanded_paths.append(path)

        if not expanded_paths:
            raise DellCLIError(
                title="API Spec Files Missing",
                cause=f"No specs found in provided paths",
                impact="Clustering pipeline cannot be initiated.",
                action="Provide valid paths via --specs option.",
            )
            
        try:
            init_db_sync()
            all_endpoints = []
            spec_titles = []
            
            for path in expanded_paths:
                ext = path.suffix.lower()
                if ext in [".graphql", ".gql"]:
                    parser_obj = GraphQLParser(path)
                elif ext == ".proto":
                    parser_obj = gRPCParser(path)
                elif ext in [".yaml", ".yml", ".json"]:
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
                    continue
                    
                contract_a = parser_obj.parse_and_flatten()
                all_endpoints.extend(contract_a.endpoints)
                spec_titles.append(contract_a.spec_title)
                
            merged_contract_a = ContractA(
                spec_title=" | ".join(spec_titles),
                spec_version="1.0.0",
                openapi_version="N/A",
                source_file="Multi-API",
                total_endpoints=len(all_endpoints),
                endpoints=all_endpoints
            )

            # Run graph and Leiden communities sync
            from src.ai_clustering.explain import set_explain_mode

            set_explain_mode(explain)
            run_pipeline(merged_contract_a)
            return {"status": "success"}
        except Exception as e:
            raise DellCLIError(
                title="Clustering Run Failure",
                cause=str(e),
                impact="SQLite schemas were not updated with communities.",
                action="Verify syntax of OpenAPI spec or database write permissions.",
            )

    def get_summary(self) -> Dict[str, Any]:
        try:
            with get_db_connection() as conn:  # type: ignore[no-untyped-call]
                eps_count = conn.execute("SELECT COUNT(*) FROM endpoints").fetchone()[0]
                wfs_count = conn.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
                comm_count = conn.execute(
                    "SELECT COUNT(DISTINCT community_id) FROM workflows"
                ).fetchone()[0]
            return {
                "Ingested Endpoints": eps_count,
                "Discovered Workflows": wfs_count,
                "Distinct Communities": comm_count,
            }
        except Exception as e:
            raise DellCLIError(
                title="Metrics Collection Failed",
                cause=str(e),
                impact="Operational summary metrics cannot be calculated.",
                action="Ensure SQLite file is not locked.",
            )

    def get_graph_stats(self) -> Dict[str, Any]:
        try:
            with get_db_connection() as conn:  # type: ignore[no-untyped-call]
                nodes_count = conn.execute("SELECT COUNT(*) FROM endpoints").fetchone()[
                    0
                ]
                edges_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            return {"Graph Nodes": nodes_count, "Graph Edges": edges_count}
        except Exception as e:
            raise DellCLIError(
                title="Graph Diagnostics Failed",
                cause=str(e),
                impact="Relationship graph status cannot be retrieved.",
                action="Ensure governance.db exists and edges table is initialized.",
            )
