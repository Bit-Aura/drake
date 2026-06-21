import typer
import uvicorn
from drake.cli.theme import console

app = typer.Typer(help="Manage the FastAPI/FastMCP server")


@app.command("start")
def start_server(
    ctx: typer.Context,
    host: str = typer.Option(
        "127.0.0.1", "--host", "-h", help="Host binding IP address"
    ),
    port: int = typer.Option(
        8000, "--port", "-p", help="Port to bind the server to"
    ),
    reload: bool = typer.Option(
        False, "--reload", help="Enable auto-reload for development"
    ),
) -> None:
    """Start the FastAPI/FastMCP proxy server using Uvicorn."""
    wrapper = ctx.obj
    if wrapper and wrapper.context.json_output:
        import json
        print(json.dumps({"event": "server_starting", "host": host, "port": port}))
    else:
        console.print(
            f"[bold green]Starting Dell Enterprise MCP Proxy Server...[/bold green]"
        )
        console.print(f"[info]Host:[/info] {host}")
        console.print(f"[info]Port:[/info] {port}")
        console.print(f"[info]Auto-reload:[/info] {reload}")
        console.print(f"[info]FastMCP endpoints available at http://{host}:{port}/mcp[/info]")
        console.print(f"[info]Press Ctrl+C to stop.[/info]\n")

    uvicorn.run("drake.proxy.server:app", host=host, port=port, reload=reload)
