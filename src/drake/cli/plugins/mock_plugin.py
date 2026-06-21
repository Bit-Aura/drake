
import typer
app = typer.Typer(help="Mock Plugin Subcommand")
@app.command("hello")
def hello():
    print("Mock hello")
