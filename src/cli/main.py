# ruff: noqa: E402
import sys
from pathlib import Path

# Add project root to sys.path for global script execution path mapping
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import time  # noqa: E402
import click  # noqa: E402
import typer  # noqa: E402
from src.cli.context import CLIContext  # noqa: E402
from src.cli.container import CLIContainer  # noqa: E402
from src.cli.exceptions import DellCLIError  # noqa: E402
from src.cli.theme import render_error, render_json, get_banner, console  # noqa: E402

app = typer.Typer(
    name="drake",
    help="Drake — Dell Enterprise MCP Workflow Proxy CLI",
    no_args_is_help=True,
)


class CLIWrapper:
    def __init__(self, context: CLIContext, container: CLIContainer):
        self.context = context
        self.container = container


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    json: bool = typer.Option(
        False, "--json", help="Enable machine-readable JSON mode"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose outputs"
    ),
    debug: bool = typer.Option(
        False, "--debug", help="Enable full debug mode with tracebacks"
    ),
) -> None:
    """Drake — Dell Enterprise MCP Workflow Proxy CLI control plane."""
    if ctx.invoked_subcommand is None and not json:
        console.print(get_banner())

    context = CLIContext(verbose=verbose, json_output=json, debug=debug)
    container = CLIContainer()
    ctx.obj = CLIWrapper(context, container)


# Add subcommands from routing modules
from src.cli.commands.cluster import app as cluster_app  # noqa: E402
from src.cli.commands.governance import app as governance_app  # noqa: E402
from src.cli.commands.compatibility import app as compatibility_app  # noqa: E402
from src.cli.commands.runtime import app as runtime_app  # noqa: E402
from src.cli.commands.ansible import app as ansible_app  # noqa: E402
from src.cli.commands.audit import app as audit_app  # noqa: E402
from src.cli.commands.system import app as system_app  # noqa: E402
from src.cli.commands.diagnostics import app as diagnostics_app  # noqa: E402
from src.cli.commands.server import app as server_app  # noqa: E402
from src.cli.commands.config import app as config_app  # noqa: E402
from src.cli.commands.pipeline import pipeline_cmd  # noqa: E402
from src.cli.plugins import load_plugins  # noqa: E402

app.add_typer(cluster_app, name="cluster")
app.add_typer(governance_app, name="governance")
app.add_typer(compatibility_app, name="compatibility")
app.add_typer(runtime_app, name="runtime")
app.add_typer(ansible_app, name="ansible")
app.add_typer(audit_app, name="audit")
app.add_typer(system_app, name="system")
app.add_typer(diagnostics_app, name="diagnostics")
app.add_typer(server_app, name="server")
app.add_typer(config_app, name="config")
app.command(name="pipeline", help="Run the complete pipeline: Ingest -> Cluster -> Serve")(pipeline_cmd)  # noqa: E501

load_plugins(app)


@app.command("overview")
def overview(
    ctx: typer.Context,
    watch: bool = typer.Option(False, "--watch", help="Watch dashboard in real-time"),
    interval: int = typer.Option(
        5, "--interval", "-i", help="Watch update interval in seconds"
    ),
) -> None:
    """Display the executive overview control panel dashboard."""
    wrapper = ctx.obj

    def run_once() -> None:
        metrics = wrapper.container.system_service.get_overview_metrics()
        if wrapper.context.json_output:
            render_json(metrics)
        else:
            from src.cli.components import render_platform_overview_dashboard

            render_platform_overview_dashboard(metrics)

    if watch:
        try:
            while True:
                if not wrapper.context.json_output:
                    click.clear()
                run_once()
                time.sleep(interval)
        except KeyboardInterrupt:
            if not wrapper.context.json_output:
                from src.cli.theme import console

                console.print("\n[info]Exiting watch mode.[/info]")
    else:
        run_once()


@app.command("health")
def health(
    ctx: typer.Context,
    watch: bool = typer.Option(
        False, "--watch", help="Watch health metrics in real-time"
    ),
    interval: int = typer.Option(
        5, "--interval", "-i", help="Watch update interval in seconds"
    ),
) -> None:
    """Display the platform subsystems health status Matrix."""
    wrapper = ctx.obj

    def run_once() -> None:
        health_status = wrapper.container.diagnostics_service.get_health_status()
        if wrapper.context.json_output:
            render_json(health_status)
        else:
            from src.cli.components import render_health_matrix

            render_health_matrix(health_status)

    if watch:
        try:
            while True:
                if not wrapper.context.json_output:
                    click.clear()
                run_once()
                time.sleep(interval)
        except KeyboardInterrupt:
            if not wrapper.context.json_output:
                from src.cli.theme import console

                console.print("\n[info]Exiting watch mode.[/info]")
    else:
        run_once()


def main() -> None:
    """Main CLI entrypoint with centralized error formatting and crash shielding."""
    try:
        app()
    except DellCLIError as e:
        render_error(e.title, e.cause, e.impact, e.action)
        sys.exit(1)
    except Exception as e:
        import traceback

        if "--debug" in sys.argv:
            traceback.print_exc()
        else:
            render_error(
                title="Unexpected Application Failure",
                cause=str(e),
                impact="The CLI execution halted abnormally.",
                action="Run the command with --debug to display full traceback, or contact administrator.",  # noqa: E501
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
