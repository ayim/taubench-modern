import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlencode, urlparse

import click
import httpx
import structlog
import yaml
from dotenv import load_dotenv

from agent_platform.quality.models import ThreadResult
from agent_platform.quality.oauth import OAuthRedirectServer
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


@dataclass
class OAuthProviderConfig:
    client_id: str
    client_secret: str
    auth_url: str
    token_url: str
    redirect_uri: str


@dataclass
class Context:
    # TODO it is used if there is an already running agent server
    # since we now can run as executable we should also verify
    # if the running server has been started with the right executable
    agent_server_url: str
    agents_dir: Path
    threads_dir: Path
    oauth: dict[str, OAuthProviderConfig]
    verbose: bool
    quality_folder: Path
    is_in_github_actions: bool


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
    "--home-folder",
    type=click.Path(exists=False, file_okay=False, path_type=Path),
    help="Sema4ai home folder",
)
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
    home_folder: Path,
    server_url: str,
    test_threads_dir: Path,
    test_agents_dir: Path,
    verbose: bool,
    show_env: bool,
):
    """Quality testing CLI for agent platform."""
    if ctx.invoked_subcommand == "init":
        return

    setup_logging(verbose)

    if verbose or show_env:
        load_env_file(verbose=True)
    else:
        load_env_file(verbose=False)

    home_folder = home_folder if home_folder is not None else Path.home() / ".sema4x"
    quality_folder = home_folder / "quality"

    if not quality_folder.exists():
        raise ValueError(f"Cannot find quality folder in {home_folder}. Did you run 'init'?")

    def load_config():
        config_file = quality_folder / "config.yaml"

        with open(config_file) as f:
            return yaml.safe_load(f)

    config = load_config()

    ctx.obj = Context(
        agent_server_url=server_url,
        quality_folder=quality_folder,
        agents_dir=test_agents_dir,
        threads_dir=test_threads_dir,
        oauth={
            provider: OAuthProviderConfig(
                client_id=data["client_id"],
                client_secret=data["client_secret"],
                auth_url=data["auth_url"],
                token_url=data["token_url"],
                redirect_uri=data["redirect_uri"],
            )
            for provider, data in config["oauth"].items()
        },
        verbose=verbose,
        is_in_github_actions=os.getenv("GITHUB_ACTIONS") == "true",
    )


@cli.command()
@click.option(
    "--home-folder",
    type=click.Path(exists=False, file_okay=False, path_type=Path),
    help="Home folder for Sema4ai",
)
async def init(home_folder):
    """Prepare the environment."""
    if home_folder is None:
        user_home_folder = Path.home()
        home_folder = user_home_folder / ".sema4x"

    quality_folder = home_folder / "quality"
    quality_folder.mkdir(parents=True, exist_ok=False)

    default_config = {
        "oauth": {},
    }
    config_file = quality_folder / "config.yaml"
    if not config_file.exists():
        with open(config_file, "w") as file:
            yaml.dump(default_config, file, default_flow_style=False)

    click.echo(f"✅ Quality tool inititialized at {quality_folder}")


@cli.command()
@click.pass_obj
async def check_server(ctx: Context):
    """Check if the agent server is available."""
    server_url = ctx.agent_server_url

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
@click.pass_obj
def list_agents(ctx: Context):
    """List available agent packages."""

    runner = QualityTestRunner(
        datadir=ctx.quality_folder,
        test_threads_dir=ctx.threads_dir,
        test_agents_dir=ctx.agents_dir,
        server_url=ctx.agent_server_url,
        agent_server_version=None,
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
@click.pass_obj
def list_tests(ctx: Context, agent_name: str | None):
    """List available test cases, optionally filtered by agent."""
    runner = QualityTestRunner(
        datadir=ctx.quality_folder,
        test_threads_dir=ctx.threads_dir,
        test_agents_dir=ctx.agents_dir,
        server_url=ctx.agent_server_url,
        agent_server_version=None,
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
    default="",
    type=str,
    help="List of agents to run tests for (if not provided, all agents will be run)",
)
@click.option(
    "--agent-server-version",
    required=False,
    type=str,
    help="Agent server version. If none is provided, the version on the current branch is used",
)
@click.pass_obj
async def run(  # noqa: PLR0913
    ctx: Context,
    detailed: bool,
    platform_summary: bool,
    max_agents: int,
    selected_agents: str,
    agent_server_version: str | None,
):
    """Run quality tests for agents."""
    runner = QualityTestRunner(
        test_threads_dir=ctx.threads_dir,
        test_agents_dir=ctx.agents_dir,
        server_url=ctx.agent_server_url,
        datadir=ctx.quality_folder,
        agent_server_version=agent_server_version,
        is_in_github_actions=ctx.is_in_github_actions,
    )

    reporter = QualityReporter()

    try:
        click.echo(
            f"🚀 Running tests for all agents (fully parallel, max {max_agents} concurrent agents)"
        )
        all_results = await runner.run_tests_for_all_agents_fully_parallel(
            selected_agents=[
                selected.strip() for selected in selected_agents.split(",") if selected.strip()
            ],
            max_concurrent_agents=max_agents,
        )

        # Report results
        if detailed:
            reporter.report_detailed_results(all_results)
        elif platform_summary:
            reporter.report_platform_summary(all_results)
        else:
            reporter.report_results(all_results)

        results_dir = runner.results_manager.get_results_dir()
        click.echo(f"💾 Results automatically saved to {results_dir}")

        def any_failures(results: dict[str, list[ThreadResult]]) -> bool:
            """Return True if at least one ThreadResult was not successful."""
            return any(
                not thread.success for thread_list in results.values() for thread in thread_list
            )

        if any_failures(all_results):
            click.echo("❌ Some tests failed", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error running test suite: {e}")
        if ctx.verbose:
            import traceback

            traceback.print_exc()
        raise click.Abort() from None


@cli.command()
@click.pass_obj
async def oauth(ctx: Context):
    """Obtain access token for oauth connections used in tests."""

    # TODO rename or create a new class: this sounds more like a "manager" than the runner itself
    runner = QualityTestRunner(
        test_threads_dir=ctx.threads_dir,
        test_agents_dir=ctx.agents_dir,
        server_url=ctx.agent_server_url,
        datadir=ctx.quality_folder,
        agent_server_version=None,
    )

    oauth_connections = await runner.get_oauth_connections()

    for provider, scopes in oauth_connections.items():
        scope_names = list(scopes.keys())
        uses = scopes.values()
        provider_actions = [item["action"] for use in uses for item in use]
        scope = " ".join(scope_names)

        if provider not in ctx.oauth:
            raise click.UsageError(
                f"👤 Provider '{provider}' not found in config. Required in 🔧 {provider_actions}"
            )

        cfg = ctx.oauth[provider]
        auth_params = {
            "response_type": "code",
            "client_id": cfg.client_id,
            "redirect_uri": cfg.redirect_uri,
            "scope": scope,
        }
        auth_url = f"{cfg.auth_url}?{urlencode(auth_params)}"

        click.echo("OAuth Authorization Required for:\n")
        click.echo(f"👤 Provider:\t '{provider}'")
        click.echo(f"🔧 Actions:\t '{provider_actions}'")
        click.echo(f"🌐 Scopes:\t '{scope}'")
        click.echo(f"\nOpen this URL in your browser to authorize:\n{auth_url}")

        parsed_url = urlparse(cfg.redirect_uri)
        redirect_host = parsed_url.hostname
        redirect_port = parsed_url.port
        if redirect_host is None or redirect_port is None:
            raise click.UsageError(f"Cannot parse redirect uri {cfg.redirect_uri}.")

        # TODO keep the server up until all the oauth connections are not processed
        server = OAuthRedirectServer(host=redirect_host, port=redirect_port)
        print("Waiting for OAuth authorization...")

        auth_code = server.wait_for_code(timeout=180)

        click.echo(f"Received authorization code: {auth_code}")

        token_data = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": cfg.redirect_uri,
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret,
        }

        try:
            with httpx.Client() as client:
                response = client.post(cfg.token_url, data=token_data)
                response.raise_for_status()
                credentials = response.json()
        except httpx.HTTPStatusError as e:
            click.echo(f"HTTP error: {e.response.status_code} - {e.response.text}", err=True)
            return
        except httpx.RequestError as e:
            click.echo(f"Request failed: {e}", err=True)
            return

        click.echo("Updating OAuth Credentials")
        await runner.oauth.update_oauth_credentials(provider=provider, credentials=credentials)


# Async wrapper for Click commands
def async_command(f):
    """Decorator to make Click commands async-compatible."""

    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper


# Apply async wrapper to async commands
check_server.callback = async_command(check_server.callback)
run.callback = async_command(run.callback)
oauth.callback = async_command(oauth.callback)
init.callback = async_command(init.callback)


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
