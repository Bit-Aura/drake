import typer
import time
from pathlib import Path
from drake.cli.theme import render_success, render_panel
from drake.cli.components import status_spinner
from drake.cli.commands.server import start_server
import asyncio

async def _inject_simulated_rollback_workflows():
    import datetime
    from drake.core.database import async_session, Workflow, EndpointStep
    from sqlalchemy import delete

    workflows_data = [
        {
            "id": "wf_dual_bank",
            "name": "firmware_update_test",
            "display": "Firmware Partition Update",
            "strategy": "DUAL_BANK",
            "supports": True,
        },
        {
            "id": "wf_scp_snapshot",
            "name": "bios_config_test",
            "display": "BIOS Settings Provisioning",
            "strategy": "SCP_SNAPSHOT",
            "supports": True,
        },
        {
            "id": "wf_none",
            "name": "factory_reset_test",
            "display": "Factory Reset Server",
            "strategy": "NONE",
            "supports": False,
        },
    ]

    async with async_session() as session:
        for wf_info in workflows_data:
            await session.execute(delete(Workflow).where(Workflow.id == wf_info["id"]))
            
            step = EndpointStep(
                workflow_id=wf_info["id"],
                step_order=1,
                method="POST",
                url=f"/redfish/v1/Systems/1/Actions/{wf_info['name']}",
                operation_id=f"Op_{wf_info['name']}",
                required_params="[]",
                created_at=datetime.datetime.now().isoformat(),
            )
            
            wf = Workflow(
                id=wf_info["id"],
                system_name=wf_info["name"],
                display_name=wf_info["display"],
                risk_level="high",
                cluster_size=1,
                confidence=0.95,
                generated_description=f"Simulated workflow with strategy {wf_info['strategy']}",
                approved=1,
                supports_rollback=wf_info["supports"],
                rollback_strategy=wf_info["strategy"],
                steps=[step],
            )
            session.add(wf)
        await session.commit()


def pipeline_cmd(  # noqa: E302
    ctx: typer.Context,
    spec: str = typer.Argument(..., help="Path to OpenAPI spec YAML/JSON"),
    auto_approve: bool = typer.Option(False, "--auto-approve", help="Auto-approve all READ_ONLY workflows"),  # noqa: E501
    serve: bool = typer.Option(False, "--serve", help="Start the server after clustering"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind the server to (if --serve is used)"),  # noqa: E501
    explain: bool = typer.Option(False, "--explain", help="Use AI to generate human-readable workflow names"),  # noqa: E501
) -> None:
    """Run the complete pipeline: Ingest -> Cluster -> (Optionally) Serve."""
    wrapper = ctx.obj

    # 1. Ingest and Cluster
    with status_spinner(f"Ingesting {spec} and discovering workflow clusters..."):
        wrapper.container.cluster_service.run_clustering([Path(spec)], explain)

    render_success("Phase 1: OpenAPI clustering completed successfully.")

    with status_spinner("Injecting simulated rollback test workflows..."):
        asyncio.run(_inject_simulated_rollback_workflows())

    # 2. Optional Auto-Approval
    if auto_approve:
        with status_spinner("Auto-approving safe LOW risk workflows..."):
            pending = wrapper.container.governance_service.get_pending()
            approved_count = 0
            for wf in pending:
                # The CLI service maps risk_level to riskLevel in get_pending()
                if wf.get("riskLevel") == "low":
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
        time.sleep(1) # Give the user a moment to read the results  # noqa: E261
        ctx.invoke(start_server, host="127.0.0.1", port=port, reload=False)
