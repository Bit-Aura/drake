import typer
import time
from pathlib import Path
from drake.cli.theme import render_success, render_panel
from drake.cli.components import status_spinner
from drake.cli.commands.server import start_server

def pipeline_cmd(
    ctx: typer.Context,
    spec: str = typer.Argument(..., help="Path to OpenAPI spec YAML/JSON"),
    auto_approve: bool = typer.Option(False, "--auto-approve", help="Auto-approve all READ_ONLY workflows"),
    serve: bool = typer.Option(False, "--serve", help="Start the server after clustering"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind the server to (if --serve is used)"),
    explain: bool = typer.Option(False, "--explain", help="Use AI to generate human-readable workflow names"),
) -> None:
    """Run the complete pipeline: Ingest -> Cluster -> (Optionally) Serve."""
    wrapper = ctx.obj
    
    # 1. Ingest and Cluster
    with status_spinner(f"Ingesting {spec} and discovering workflow clusters..."):
        wrapper.container.cluster_service.run_clustering(Path(spec), explain)
        
    render_success("Phase 1: OpenAPI clustering completed successfully.")
    
    # 2. Optional Auto-Approval
    if auto_approve:
        with status_spinner("Auto-approving safe READ_ONLY workflows..."):
            pending = wrapper.container.governance_service.get_pending()
            approved_count = 0
            for wf in pending:
                if wf.get("riskLevel") == "READ_ONLY":
                    wrapper.container.governance_service.approve_workflow(wf["id"])
                    approved_count += 1
                    
        render_success(f"Phase 2: Auto-approved {approved_count} READ_ONLY workflows.")
    
    # Summary
    summary = wrapper.container.cluster_service.get_summary()
    content = (
        f"[bold white]Ingested Endpoints :[/bold white] {summary.get('Ingested Endpoints', 0)}\n"
        f"[bold white]Discovered Workflows:[/bold white] {summary.get('Discovered Workflows', 0)}"
    )
    from drake.cli.theme import console
    console.print(render_panel(content, title="Pipeline Result", border_style="cyan"))
    
    # 3. Optional Serve
    if serve:
        console.print("[bold yellow]Phase 3: Starting Drake FastMCP Server...[/bold yellow]")
        time.sleep(1) # Give the user a moment to read the results
        ctx.invoke(start_server, host="127.0.0.1", port=port, reload=False)
