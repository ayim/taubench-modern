import asyncio
import logging
from http import HTTPStatus
from pathlib import Path

import click
import httpx
import structlog
from dotenv import load_dotenv

from agent_platform.quality.reporter import QualityReporter
from agent_platform.quality.runner import QualityTestRunner

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


def setup_logging(verbose: bool = False):
    """Setup structured logging."""
    if verbose:
        # JSON structured logging for verbose mode
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        logging.basicConfig(level=logging.DEBUG)
    else:
        # Simple logging for normal mode
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.dev.ConsoleRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        logging.basicConfig(level=logging.INFO)


@click.group()
@click.option(
    "--server-url",
    default="http://localhost:8000",
    envvar="AGENT_SERVER_URL",
    help="Agent server URL",
)
@click.option(
    "--test-threads-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("quality/test-threads"),
    help="Directory containing test thread YAML files",
)
@click.option(
    "--test-agents-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("quality/test-agents"),
    help="Directory containing agent ZIP packages",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--show-env", is_flag=True, help="Show loaded .env file location")
@click.pass_context
def cli(  # noqa: PLR0913
    ctx,
    server_url: str,
    test_threads_dir: Path,
    test_agents_dir: Path,
    verbose: bool,
    show_env: bool,
):
    """Quality testing CLI for agent platform."""
    setup_logging(verbose)

    # Load .env file from monorepo root
    if verbose or show_env:
        load_env_file(verbose=True)
    else:
        load_env_file(verbose=False)

    ctx.ensure_object(dict)
    ctx.obj["server_url"] = server_url
    ctx.obj["test_threads_dir"] = test_threads_dir
    ctx.obj["test_agents_dir"] = test_agents_dir
    ctx.obj["verbose"] = verbose


@cli.command()
@click.pass_context
async def check_server(ctx):
    """Check if the agent server is available."""
    server_url = ctx.obj["server_url"]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{server_url}/health", timeout=5.0)
            if response.status_code == HTTPStatus.OK:
                click.echo(f"✅ Agent server is available at {server_url}")
                return True
            else:
                click.echo(f"❌ Agent server returned status {response.status_code}")
                return False
    except Exception as e:
        click.echo(f"❌ Failed to connect to agent server: {e}")
        return False


@cli.command()
@click.pass_context
def list_agents(ctx):
    """List available agent packages."""
    test_agents_dir = ctx.obj["test_agents_dir"]

    runner = QualityTestRunner(
        test_threads_dir=ctx.obj["test_threads_dir"],
        test_agents_dir=test_agents_dir,
        server_url=ctx.obj["server_url"],
    )

    agents = runner.discover_agents()

    if not agents:
        click.echo("No agent packages found.")
        return

    click.echo(f"Found {len(agents)} agent packages:")
    for agent in agents:
        click.echo(f"  • {agent.name} ({agent.zip_path})")


@cli.command()
@click.argument("agent_name", required=False)
@click.pass_context
def list_tests(ctx, agent_name: str | None):
    """List available test cases, optionally filtered by agent."""
    runner = QualityTestRunner(
        test_threads_dir=ctx.obj["test_threads_dir"],
        test_agents_dir=ctx.obj["test_agents_dir"],
        server_url=ctx.obj["server_url"],
    )

    test_cases = runner.discover_test_cases(agent_name)

    if not test_cases:
        if agent_name:
            click.echo(f"No test cases found for agent: {agent_name}")
        else:
            click.echo("No test cases found.")
        return

    if agent_name:
        click.echo(f"Found {len(test_cases)} test cases for agent {agent_name}:")
    else:
        click.echo(f"Found {len(test_cases)} test cases:")

    for test_case in test_cases:
        click.echo(f"  • {test_case.thread.name} ({test_case.file_path})")
        if test_case.evaluations:
            click.echo(f"    Evaluations: {len(test_case.evaluations)}")
            for evaluation in test_case.evaluations:
                click.echo(f"      - {evaluation.kind}")


@cli.command()
@click.option("--detailed", is_flag=True, help="Show detailed evaluation results")
@click.option("--platform-summary", is_flag=True, help="Show platform-focused summary")
@click.option(
    "--max-agents",
    default=3,
    type=int,
    help="Maximum number of agents to run concurrently",
)
@click.option(
    "--selected-agents",
    default=[],
    type=list[str],
    help="List of agents to run tests for (if not provided, all agents will be run)",
)
@click.pass_context
async def run(
    ctx,
    detailed: bool,
    platform_summary: bool,
    max_agents: int,
    selected_agents: list[str],
):
    """Run quality tests for agents."""
    # Get datadir from orchestrator's default location if not specified
    from agent_platform.quality.orchestrator import QualityOrchestrator

    temp_orchestrator = QualityOrchestrator()
    datadir = temp_orchestrator.data_dir

    runner = QualityTestRunner(
        test_threads_dir=ctx.obj["test_threads_dir"],
        test_agents_dir=ctx.obj["test_agents_dir"],
        server_url=ctx.obj["server_url"],
        datadir=datadir,
    )

    reporter = QualityReporter()

    try:
        click.echo(
            f"🚀 Running tests for all agents (fully parallel, max {max_agents} concurrent agents)"
        )
        all_results = await runner.run_tests_for_all_agents_fully_parallel(
            selected_agents=selected_agents,
            max_concurrent_agents=max_agents,
        )

        # Report results
        if detailed:
            reporter.report_detailed_results(all_results)
        elif platform_summary:
            reporter.report_platform_summary(all_results)
        else:
            reporter.report_results(all_results)

        # Results are automatically saved to datadir by QualityResultsManager
        results_dir = runner.results_manager.get_results_dir()
        click.echo(f"💾 Results automatically saved to {results_dir}")

    except Exception as e:
        click.echo(f"Error running test suite: {e}")
        if ctx.obj["verbose"]:
            import traceback

            traceback.print_exc()
        raise click.Abort() from None


# Async wrapper for Click commands
def async_command(f):
    """Decorator to make Click commands async-compatible."""

    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


# Apply async wrapper to async commands
check_server.callback = async_command(check_server.callback)
run.callback = async_command(run.callback)


def find_monorepo_root() -> Path:
    """Find the monorepo root by looking for markers like .git directory."""
    current = Path.cwd()

    # Walk up the directory tree looking for the monorepo root
    while current != current.parent:
        # Check for common monorepo markers
        if (current / ".git").is_dir() or (current / "pyproject.toml").is_file():
            # Additional check: ensure this is the agent-platform monorepo
            # by looking for the quality directory
            if (current / "quality").is_dir():
                return current
        current = current.parent

    # Fallback to current working directory
    return Path.cwd()


def load_env_file(verbose: bool = False):
    """Load .env file from the monorepo root if it exists."""
    monorepo_root = find_monorepo_root()
    env_file = monorepo_root / ".env"

    # First, if it exists, load the .env file in the quality directory
    quality_env_file = monorepo_root / "quality" / ".env"
    if quality_env_file.is_file():
        load_dotenv(quality_env_file)
        if verbose:
            click.echo(f"📄 Loaded environment variables from: {quality_env_file}")

    # Then, it _must_ exist, load the .env file in the monorepo root
    if env_file.is_file():
        load_dotenv(env_file)
        if verbose:
            click.echo(f"📄 Loaded environment variables from: {env_file}")
        return str(env_file)
    else:
        # .env file is required for operation
        click.echo(f"❌ Error: Required .env file not found at: {env_file}", err=True)
        click.echo(
            "💡 Please create a .env file in the monorepo root using `make new-empty-env`",
            err=True,
        )
        raise click.ClickException(f"Required .env file not found at: {env_file}")


def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
